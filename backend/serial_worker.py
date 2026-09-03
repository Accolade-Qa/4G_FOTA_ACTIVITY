"""Serial Communication Worker Module.

Asynchronous serial log reader utilizing PySerial inside a standard Python threading.Thread.
Triggers callback functions for real-time console logging, login packet detection,
and FOTA download progress. Integrates TelemetryAccumulator for multi-line reboot logs.
"""

import time
import logging
import threading
from typing import List, Optional, Callable
import serial
import serial.tools.list_ports

from backend.message_parser import MessageParser, TelemetryAccumulator
from backend.models import LoginPacketInfo

logger = logging.getLogger(__name__)


class PortInfoDetail:
    """Dataclass storing COM port hardware information and Bluetooth classification."""

    def __init__(self, device: str, description: str, hwid: str):
        self.device = device
        self.description = description or ""
        self.hwid = hwid or ""
        desc_lower = self.description.lower()
        hwid_lower = self.hwid.lower()
        self.is_bluetooth = ("bluetooth" in desc_lower or "bth" in desc_lower or "bthenum" in hwid_lower or "bth" in hwid_lower)

    @property
    def display_text(self) -> str:
        short_desc = self.description
        if "(" in short_desc and ")" in short_desc:
            short_desc = short_desc.split("(")[0].strip()
        if self.is_bluetooth:
            return f"{self.device} [Bluetooth] - {short_desc or 'Bluetooth Link'}"
        return f"{self.device} [Serial] - {short_desc or 'Serial Port'}"


class SerialWorker(threading.Thread):
    """Background Thread listening to serial COM port data streams."""

    def __init__(
        self,
        port_name: str = "",
        baud_rate: int = 115200,
        on_raw_log: Optional[Callable[[str], None]] = None,
        on_login_packet: Optional[Callable[[LoginPacketInfo], None]] = None,
        on_progress: Optional[Callable[[float], None]] = None,
        on_sleep_countdown: Optional[Callable[[int], None]] = None,
        on_sleep_event: Optional[Callable[[str], None]] = None,
        on_port_status: Optional[Callable[[bool, str], None]] = None,
    ) -> None:
        super().__init__(daemon=True)
        self.port_name = port_name
        self.baud_rate = baud_rate
        self.on_raw_log = on_raw_log
        self.on_login_packet = on_login_packet
        self.on_progress = on_progress
        self.on_sleep_countdown = on_sleep_countdown
        self.on_sleep_event = on_sleep_event
        self.on_port_status = on_port_status

        self._running = False
        self._serial_inst: Optional[serial.Serial] = None
        self._captured_login = False
        self.accumulator = TelemetryAccumulator()

    @staticmethod
    def list_detailed_ports() -> List[PortInfoDetail]:
        """Discover connected COM ports and classify physical Serial vs Bluetooth ports."""
        ports = serial.tools.list_ports.comports()
        result = []
        for p in ports:
            result.append(PortInfoDetail(device=p.device, description=p.description, hwid=p.hwid))
        return result

    @staticmethod
    def list_available_ports() -> List[str]:
        """Discover connected serial COM ports."""
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def stop(self) -> None:
        """Signal thread to stop reading and close port cleanly."""
        self._running = False
        if self._serial_inst:
            try:
                if self._serial_inst.is_open:
                    self._serial_inst.close()
            except Exception as e:
                logger.warning("Error closing serial port: %s", e)

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
                msg = "No COM ports found. Please connect device and retry."
                logger.error(msg)
                if self.on_port_status:
                    self.on_port_status(False, msg)
                return

        try:
            self._serial_inst = serial.Serial(
                port=target_port,
                baudrate=self.baud_rate,
                timeout=1.0,
            )
            logger.info("Opened serial port %s at %d baud", target_port, self.baud_rate)
            if self.on_port_status:
                self.on_port_status(True, f"Connected: {target_port} ({self.baud_rate} baud)")
        except Exception as err:
            errMsg = f"Failed to open port {target_port}: {err}"
            logger.error(errMsg)
            if self.on_port_status:
                self.on_port_status(False, errMsg)
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
                        # Raw log callback
                        if self.on_raw_log:
                            self.on_raw_log(cleaned)

                        # Check for FOTA download progress percentage
                        prog = MessageParser.parse_download_progress(cleaned)
                        if prog is not None and self.on_progress:
                            self.on_progress(prog)

                        # Check for [PLA] SLEEP countdown timer & sleep events
                        if MessageParser.is_sleep_event(cleaned) and self.on_sleep_event:
                            self.on_sleep_event(cleaned)

                        sleep_sec = MessageParser.parse_pla_sleep_countdown(cleaned)
                        if sleep_sec is not None:
                            if self.on_sleep_countdown:
                                self.on_sleep_countdown(sleep_sec)
                            if sleep_sec == 0:
                                logger.info("PLA Sleep countdown reached 0s (Soft Shutdown/Sleep). Resetting login capture for post-reboot logs.")
                                self.reset_login_capture()

                        # 1. Parse and emit genuine 55AA Login Packets
                        if "55AA" in cleaned:
                            pkts_55aa = MessageParser.parse_all_55aa_login_packets(cleaned)
                            for pkt in pkts_55aa:
                                if self.on_login_packet:
                                    self.on_login_packet(pkt)

                        # 2. Harvest telemetry across multi-line reboot logs or AT responses (*GET#PRNCFG#) for orchestrator
                        info = self.accumulator.feed_line(cleaned)
                        if info and not ("55AA" in cleaned) and self.on_login_packet:
                            self.on_login_packet(info)

            except Exception as err:
                if self._running:
                    logger.error("Serial read exception: %s", err)
                    time.sleep(0.5)

        logger.info("Serial worker thread stopped.")
