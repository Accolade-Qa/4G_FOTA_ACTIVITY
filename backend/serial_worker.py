"""Serial Communication Worker Module.

Asynchronous serial log reader utilizing PySerial inside a PyQt6 QThread.
Emits native PyQt signals for real-time UI logging, login packet detection,
and FOTA download progress. Integrates TelemetryAccumulator for multi-line reboot logs.
"""

import time
import logging
from typing import List, Optional
import serial
import serial.tools.list_ports

from PyQt6.QtCore import QThread, pyqtSignal
from backend.message_parser import MessageParser, TelemetryAccumulator
from backend.models import LoginPacketInfo

logger = logging.getLogger(__name__)


class SerialWorker(QThread):
    """Background QThread listening to serial COM port data streams."""

    # PyQt6 Signals
    raw_log_signal = pyqtSignal(str)
    login_packet_signal = pyqtSignal(object)  # LoginPacketInfo
    progress_signal = pyqtSignal(float)
    sleep_countdown_signal = pyqtSignal(int)
    sleep_event_signal = pyqtSignal(str)
    port_status_signal = pyqtSignal(bool, str)

    def __init__(self, port_name: str = "", baud_rate: int = 115200, parent=None) -> None:
        super().__init__(parent)
        self.port_name = port_name
        self.baud_rate = baud_rate
        self._running = False
        self._serial_inst: Optional[serial.Serial] = None
        self._captured_login = False
        self.accumulator = TelemetryAccumulator()

    @staticmethod
    def list_available_ports() -> List[str]:
        """Discover connected serial COM ports."""
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def stop(self) -> None:
        """Signal thread to stop reading and close port."""
        self._running = False
        if self._serial_inst and self._serial_inst.is_open:
            try:
                self._serial_inst.close()
            except Exception as e:
                logger.warning("Error closing serial port: %s", e)
        self.wait(2000)

    def reset_login_capture(self) -> None:
        """Reset captured login packet flag and accumulator for new upgrade cycle."""
        self._captured_login = False
        self.accumulator.reset()

    def send_command(self, cmd: str) -> bool:
        """Send command string over active serial connection to hardware device."""
        if self._serial_inst and self._serial_inst.is_open:
            try:
                if not cmd.endswith("\r") and not cmd.endswith("\n"):
                    cmd += "\r\n"
                self._serial_inst.write(cmd.encode("utf-8"))
                logger.info("Sent serial command: %s", cmd.strip())
                # If command is reset/reboot, reset accumulator to harvest fresh boot logs
                if "CRST" in cmd or "RESET" in cmd or "REBOOT" in cmd:
                    self.reset_login_capture()
                return True
            except Exception as e:
                logger.error("Failed to write to serial port: %s", e)
        else:
            logger.warning("Cannot send command '%s': Serial port is not open.", cmd)
        return False

    def run(self) -> None:
        """Main thread loop for opening port and parsing lines."""
        self._running = True
        target_port = self.port_name

        # Auto-detect COM port if not specified
        if not target_port:
            available = self.list_available_ports()
            if available:
                target_port = available[0]
                logger.info("Auto-detected COM port: %s", target_port)
            else:
                msg = "No COM ports found. Please connect device and refresh."
                logger.error(msg)
                self.port_status_signal.emit(False, msg)
                return

        try:
            self._serial_inst = serial.Serial(
                port=target_port,
                baudrate=self.baud_rate,
                timeout=1.0,
            )
            logger.info("Opened serial port %s at %d baud", target_port, self.baud_rate)
            self.port_status_signal.emit(True, f"Connected: {target_port} ({self.baud_rate} baud)")
        except Exception as err:
            errMsg = f"Failed to open port {target_port}: {err}"
            logger.error(errMsg)
            self.port_status_signal.emit(False, errMsg)
            return

        buffer = ""
        while self._running and self._serial_inst and self._serial_inst.is_open:
            try:
                data = self._serial_inst.read(self._serial_inst.in_waiting or 1)
                if not data:
                    continue

                chunk = data.decode("utf-8", errors="replace")
                chunk = chunk.replace("\r\n", "\n").replace('\r', '\n')
                buffer += chunk

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    cleaned = MessageParser.strip_ansi(line).strip()

                    if cleaned:
                        # Emit raw log for UI terminal view
                        self.raw_log_signal.emit(cleaned)

                        # Check for FOTA download progress percentage
                        prog = MessageParser.parse_download_progress(cleaned)
                        if prog is not None:
                            self.progress_signal.emit(prog)

                        # Check for [PLA] SLEEP countdown timer & sleep events
                        if MessageParser.is_sleep_event(cleaned):
                            self.sleep_event_signal.emit(cleaned)

                        sleep_sec = MessageParser.parse_pla_sleep_countdown(cleaned)
                        if sleep_sec is not None:
                            self.sleep_countdown_signal.emit(sleep_sec)
                            if sleep_sec == 0:
                                logger.info("PLA Sleep countdown reached 0s (Soft Shutdown/Sleep). Resetting login capture for post-reboot logs.")
                                self.reset_login_capture()

                        # Harvest telemetry across multi-line reboot logs
                        info = self.accumulator.feed_line(cleaned)
                        if info:
                            self.login_packet_signal.emit(info)

            except Exception as err:
                if self._running:
                    logger.error("Serial read exception: %s", err)
                    time.sleep(0.5)

        logger.info("Serial worker thread stopped.")
