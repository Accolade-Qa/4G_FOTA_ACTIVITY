"""Minimalist Desktop UI Interface Main Window Controller.

Provides light theme styling, interactive serial AT command sending with Up/Down arrow history,
smart auto-scroll, state selection dropdown, and automated CIP2 QA server verification and reboot handling.
Imports modular UI widgets from ui.widgets.
"""

import json
import sys
import logging
from pathlib import Path
from typing import Optional, List

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import os
import sys
from pathlib import Path

# Add repo root to Python path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import Config
from backend.models import LoginPacketInfo
from backend.orchestrator import FotaOrchestrator
from backend.serial_worker import SerialWorker
from backend.message_parser import MessageParser
from ui.styles import LIGHT_THEME_QSS, DARK_THEME_QSS
from ui.widgets import (
    ApiSyncWorker,
    CommandHistoryLineEdit,
    InteractiveTerminalConsole,
    SnackbarWidget,
)

logger = logging.getLogger(__name__)


class MinimalFotaWindow(QMainWindow):
    """Ultra-Minimalist Window with Light/Dark Theme Support & Automated Reboot/CIP2 QA Verification."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Continuous FOTA Utility")
        self.resize(1020, 650)
        self.is_dark_theme = False
        self.setStyleSheet(LIGHT_THEME_QSS)

        self.config = Config(REPO_ROOT)
        self.orchestrator = FotaOrchestrator(self.config)
        self.serial_worker: Optional[SerialWorker] = None
        self.api_sync_worker: Optional[ApiSyncWorker] = None
        self._log_buffer = []
        self._last_toast_key = None

        self._init_ui()
        self.snackbar = SnackbarWidget(self)
        self._connect_signals()
        self._populate_states_dropdown()

        # Flush buffered log lines every 50ms (prevents UI rendering lag)
        self.timer_flush = QTimer(self)
        self.timer_flush.timeout.connect(self._flush_log_buffer)
        self.timer_flush.start(50)

        # Launch API Matrix Sync asynchronously in background thread
        self.api_sync_worker = ApiSyncWorker(self.orchestrator, self)
        self.api_sync_worker.sync_done_signal.connect(self._on_api_sync_complete)
        self.api_sync_worker.start()

    def _init_ui(self) -> None:
        """Build clean light/dark interface layout."""
        root = QWidget(self)
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. Top Header Bar (Title + Online Status + Target State Dropdown + Port Select + Theme Toggle + Refresh + Start/Stop Engine)
        hdr = QFrame()
        hdr.setProperty("class", "header-bar")
        hdr_box = QHBoxLayout(hdr)
        hdr_box.setContentsMargins(12, 6, 12, 6)
        hdr_box.setSpacing(8)

        title = QLabel("FOTA UTILITY")
        title.setProperty("class", "app-title")

        self.lbl_status = QLabel("● OFFLINE")
        self.lbl_status.setProperty("class", "status-offline")

        self.combo_states = QComboBox()
        self.combo_states.setMinimumWidth(140)
        self.combo_states.currentTextChanged.connect(self._on_state_selected)

        self.combo_ports = QComboBox()
        self.combo_ports.setMinimumWidth(100)
        self._refresh_ports()

        self.btn_refresh = QPushButton("↻")
        self.btn_refresh.setProperty("class", "btn-icon")
        self.btn_refresh.setFixedWidth(32)
        self.btn_refresh.setToolTip("Refresh COM ports")
        self.btn_refresh.clicked.connect(self._refresh_ports)

        self.btn_theme = QPushButton("🌙")
        self.btn_theme.setProperty("class", "btn-icon")
        self.btn_theme.setFixedWidth(32)
        self.btn_theme.setToolTip("Toggle Dark / Light Theme")
        self.btn_theme.clicked.connect(self._toggle_theme)

        self.btn_toggle = QPushButton("Start Engine")
        self.btn_toggle.setProperty("class", "btn-primary")
        self.btn_toggle.clicked.connect(self._toggle_engine)

        hdr_box.addWidget(title)
        hdr_box.addWidget(self.lbl_status)
        hdr_box.addStretch()
        hdr_box.addWidget(QLabel("Target State:"))
        hdr_box.addWidget(self.combo_states)
        hdr_box.addWidget(QLabel("Port:"))
        hdr_box.addWidget(self.combo_ports)
        hdr_box.addWidget(self.btn_refresh)
        hdr_box.addWidget(self.btn_theme)
        hdr_box.addWidget(self.btn_toggle)

        layout.addWidget(hdr)

        # 2. Captured Telemetry Bar (IMEI, UIN, VIN, ICCID, State, Firmware + Clear Info Button)
        tel_bar = QFrame()
        tel_bar.setProperty("class", "telemetry-bar")
        tel_box = QHBoxLayout(tel_bar)
        tel_box.setContentsMargins(10, 6, 10, 6)
        tel_box.setSpacing(14)

        self.lbl_imei = self._add_stat(tel_box, "IMEI", "---")
        self.lbl_uin = self._add_stat(tel_box, "UIN", "---")
        self.lbl_vin = self._add_stat(tel_box, "VIN", "---")
        self.lbl_iccid = self._add_stat(tel_box, "ICCID", "---")
        self.lbl_state = self._add_stat(tel_box, "CURRENT STATE", "DO NOT DELETE")
        self.lbl_ver = self._add_stat(tel_box, "FIRMWARE", "---")

        btn_clear_info = QPushButton("Clear Info")
        btn_clear_info.setProperty("class", "btn-secondary")
        btn_clear_info.setFixedWidth(85)
        btn_clear_info.setToolTip("Clear captured device telemetry")
        btn_clear_info.clicked.connect(self._clear_device_telemetry)
        tel_box.addWidget(btn_clear_info, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(tel_bar)

        # 3. Status Line (Clean, padded message banner)
        self.lbl_msg = QLabel("Ready.")
        self.lbl_msg.setStyleSheet("color: #2563eb; font-size: 9pt; font-weight: 500; padding: 2px 4px;")
        self.lbl_msg.setWordWrap(True)
        layout.addWidget(self.lbl_msg)

        # 4. Interactive Log Terminal Console
        self.console = InteractiveTerminalConsole()
        layout.addWidget(self.console, stretch=1)

        # 5. Command Input Bar (Send Serial AT Commands with Up/Down Arrow History)
        cmd_box = QHBoxLayout()
        self.input_cmd = CommandHistoryLineEdit()
        self.input_cmd.setPlaceholderText("Type serial/AT command and press Enter (e.g. *SET#CRST#1#)... Use Up/Down arrow for history.")
        self.input_cmd.returnPressed.connect(self._on_send_command)

        self.btn_send_cmd = QPushButton("Send Command")
        self.btn_send_cmd.setFixedWidth(120)
        self.btn_send_cmd.clicked.connect(self._on_send_command)

        cmd_box.addWidget(self.input_cmd, stretch=1)
        cmd_box.addWidget(self.btn_send_cmd)

        layout.addLayout(cmd_box)

    def _add_stat(self, box: QHBoxLayout, label: str, default: str) -> QLabel:
        """Helper for adding compact inline telemetry stats."""
        col = QVBoxLayout()
        col.setSpacing(1)
        lbl_t = QLabel(label)
        lbl_t.setProperty("class", "stat-label")
        lbl_v = QLabel(default)
        lbl_v.setProperty("class", "stat-value")
        col.addWidget(lbl_t)
        col.addWidget(lbl_v)
        box.addLayout(col)
        return lbl_v

    def _connect_signals(self) -> None:
        """Connect orchestrator signals."""
        self.orchestrator.status_signal.connect(self.lbl_msg.setText)
        self.orchestrator.device_info_signal.connect(self._on_device_info)
        self.orchestrator.progress_signal.connect(self._on_progress_update)
        self.orchestrator.request_command_signal.connect(self._auto_execute_command)

    @pyqtSlot(float)
    def _on_progress_update(self, val: float) -> None:
        """Handle download progress update."""
        self.lbl_msg.setText(f"FOTA Downloading: {val:.1f}%")

    @pyqtSlot(bool, str)
    def _on_api_sync_complete(self, ok: bool, msg: str) -> None:
        """Callback when background API matrix sync completes."""
        self._populate_states_dropdown()
        logger.info("Background API sync completed: %s", msg)

    def _populate_states_dropdown(self) -> None:
        """Populate State Selector Dropdown dynamically from input/servers.json (API response)."""
        self.combo_states.blockSignals(True)
        self.combo_states.clear()
        
        states = ["DO NOT DELETE"]
        target_path = self.config.firmware_json_path
        if target_path.exists():
            try:
                MessageParser.load_valid_states_from_json(target_path)
                with open(target_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    st_dict = data.get("states", {})
                    for s in st_dict.keys():
                        if s not in states and s.lower() != "default":
                            states.append(s)
            except Exception as e:
                logger.warning("Error reading state names for dropdown: %s", e)

        self.combo_states.addItems(states)
        self.combo_states.setCurrentText("DO NOT DELETE")
        self.combo_states.blockSignals(False)

    @pyqtSlot(str)
    def _on_state_selected(self, state_name: str) -> None:
        """Handle state selection change from state dropdown and re-evaluate version validation."""
        if not state_name:
            return
        self.lbl_state.setText(state_name)
        if self.orchestrator and self.orchestrator.current_device:
            self.orchestrator.current_device.state = state_name
            self.orchestrator.attempted_uins.discard(self.orchestrator.current_device.uin)
            self.orchestrator.process_login_packet(self.orchestrator.current_device, selected_ui_state=state_name)

    def _refresh_ports(self) -> None:
        """Refresh COM ports dropdown."""
        self.combo_ports.clear()
        ports = SerialWorker.list_available_ports()
        if ports:
            self.combo_ports.addItems(ports)
        else:
            self.combo_ports.addItem("No Ports")

    @pyqtSlot()
    def _toggle_theme(self) -> None:
        """Toggle between Light and Dark application themes."""
        self.is_dark_theme = not getattr(self, "is_dark_theme", False)
        if self.is_dark_theme:
            self.setStyleSheet(DARK_THEME_QSS)
            self.btn_theme.setText("☀️")
            self.btn_theme.setToolTip("Switch to Light Theme")
            self.lbl_msg.setText("Dark theme enabled.")
        else:
            self.setStyleSheet(LIGHT_THEME_QSS)
            self.btn_theme.setText("🌙")
            self.btn_theme.setToolTip("Switch to Dark Theme")
            self.lbl_msg.setText("Light theme enabled.")

    @pyqtSlot()
    def _toggle_engine(self) -> None:
        """Start or stop serial engine and lock/unlock port selection controls."""
        if self.serial_worker and self.serial_worker.isRunning():
            self._stop_engine()
        else:
            self._start_engine()

    def _start_engine(self) -> None:
        """Start serial engine, lock port selection, change UI status to ONLINE, and auto-fire reboot command (*SET#CRST#1#)."""
        port = self.combo_ports.currentText()
        if port == "No Ports":
            port = ""
        
        self.serial_worker = SerialWorker(port_name=port, baud_rate=self.config.serial_baud)
        self.serial_worker.raw_log_signal.connect(self._queue_log_line)
        self.serial_worker.progress_signal.connect(self.orchestrator.update_progress)
        self.serial_worker.login_packet_signal.connect(self._on_login_packet_received)
        self.serial_worker.port_status_signal.connect(self._on_port_status)
        self.serial_worker.start()

        # Update UI Controls to ONLINE & Stop Engine
        self.combo_ports.setEnabled(False)
        self.btn_refresh.setEnabled(False)

        self.lbl_status.setText("● ONLINE")
        self.lbl_status.setProperty("class", "status-online")
        self.btn_toggle.setText("Stop")
        self.btn_toggle.setProperty("class", "btn-danger")

        self.lbl_status.setStyle(self.lbl_status.style())
        self.btn_toggle.setStyle(self.btn_toggle.style())

        # Auto-fire reboot command *SET#CRST#1# upon engine connection
        QTimer.singleShot(600, lambda: self._auto_execute_command("*SET#CRST#1#"))

    @pyqtSlot(object)
    def _on_login_packet_received(self, info: LoginPacketInfo) -> None:
        """Forward received login packet to orchestrator with user selected state."""
        sel_state = self.combo_states.currentText()
        if self.orchestrator:
            self.orchestrator.process_login_packet(info, selected_ui_state=sel_state)

    def _stop_engine(self) -> None:
        """Stop serial engine and unlock port selection."""
        if self.serial_worker:
            self.serial_worker.stop()
            self.serial_worker = None

        self.combo_ports.setEnabled(True)
        self.btn_refresh.setEnabled(True)

        self.lbl_status.setText("● OFFLINE")
        self.lbl_status.setProperty("class", "status-offline")
        self.btn_toggle.setText("Start")
        self.btn_toggle.setProperty("class", "btn-primary")

        self.lbl_status.setStyle(self.lbl_status.style())
        self.btn_toggle.setStyle(self.btn_toggle.style())

    @pyqtSlot(str)
    def _auto_execute_command(self, cmd: str) -> None:
        """Automated serial AT command execution."""
        if not cmd:
            return
        if self.serial_worker and self.serial_worker.isRunning():
            success = self.serial_worker.send_command(cmd)
            if success:
                self.console.appendPlainText(f"[TX AUTO] > {cmd}")
                sb = self.console.verticalScrollBar()
                sb.setValue(sb.maximum())
                logger.info("Auto-executed serial command: %s", cmd)

    @pyqtSlot()
    def _on_send_command(self) -> None:
        """Send serial command typed in command input bar to device."""
        cmd = self.input_cmd.text().strip()
        if not cmd:
            return

        self.input_cmd.record_command(cmd)

        if self.serial_worker and self.serial_worker.isRunning():
            success = self.serial_worker.send_command(cmd)
            if success:
                self.console.appendPlainText(f"[TX] > {cmd}")
                sb = self.console.verticalScrollBar()
                sb.setValue(sb.maximum())
                self.input_cmd.clear()
            else:
                self.lbl_msg.setText(f"Failed to send command: {cmd}")
        else:
            self.lbl_msg.setText("Cannot send command: Engine is OFFLINE.")

    @pyqtSlot()
    def _clear_device_telemetry(self) -> None:
        """Reset all captured device telemetry fields back to defaults."""
        self.lbl_imei.setText("---")
        self.lbl_uin.setText("---")
        self.lbl_vin.setText("---")
        self.lbl_iccid.setText("---")
        self.lbl_state.setText(self.combo_states.currentText() or "DO NOT DELETE")
        self.lbl_ver.setText("---")
        self._last_toast_key = None
        
        if self.orchestrator:
            self.orchestrator.reset_orchestrator()
        if self.serial_worker:
            self.serial_worker.reset_login_capture()
        self.lbl_msg.setText("Cleared captured device telemetry.")

    @pyqtSlot(bool, str)
    def _on_port_status(self, connected: bool, msg: str) -> None:
        """Handle serial connection and physical disconnect events."""
        self.lbl_msg.setText(msg)
        if not connected:
            self._stop_engine()

    @pyqtSlot(object)
    def _on_device_info(self, info: LoginPacketInfo) -> None:
        """Display captured telemetry and trigger freeze-free Snackbar Alert."""
        self.lbl_imei.setText(info.imei or "---")
        self.lbl_uin.setText(info.uin or "---")
        self.lbl_vin.setText(info.vin or "---")
        self.lbl_iccid.setText(info.iccid or "---")

        curr_state = info.state if (info.state and info.state not in ("is Factory", "connected", "---", "")) else (self.combo_states.currentText() or "DO NOT DELETE")
        self.lbl_state.setText(curr_state)
        
        target = self.orchestrator.target_version or "Latest"
        if info.version:
            self.lbl_ver.setText(f"{info.version} → {target}")
        else:
            self.lbl_ver.setText("---")

        # Trigger Snackbar ONLY ONCE when a new UIN is detected (prevents UI freeze)
        toast_key = (info.uin, info.imei)
        if info.uin and toast_key != self._last_toast_key:
            self._last_toast_key = toast_key
            toast_text = f"⚡ Device Detected: UIN {info.uin} | IMEI {info.imei}"
            self.snackbar.show_message(toast_text, duration_ms=3000)

    def _queue_log_line(self, line: str) -> None:
        """Queue incoming serial line for batch flushing and inspect for CIP2 server verification."""
        self._log_buffer.append(line)
        if self.orchestrator:
            self.orchestrator.process_log_line(line)

    def _flush_log_buffer(self) -> None:
        """Flush queued log lines without moving viewport when user is scrolled up inspecting past logs."""
        if self._log_buffer:
            sb = self.console.verticalScrollBar()
            prev_val = sb.value()
            max_val = sb.maximum()

            at_bottom = prev_val >= (max_val - 25)

            lines = "\n".join(self._log_buffer)
            self._log_buffer.clear()

            self.console.appendPlainText(lines)

            # Write terminal logs to logs/terminal_session.log
            try:
                term_log_path = self.config.logs_dir / "terminal_session.log"
                with open(term_log_path, "a", encoding="utf-8") as f:
                    f.write(lines + "\n")
            except Exception as err:
                logger.debug("Failed writing terminal log: %s", err)

            if at_bottom:
                sb.setValue(sb.maximum())
            else:
                sb.setValue(prev_val)

    def resizeEvent(self, event) -> None:
        """Reposition floating snackbar on window resize."""
        super().resizeEvent(event)
        if hasattr(self, "snackbar") and self.snackbar.isVisible():
            p_w = self.width()
            p_h = self.height()
            w = self.snackbar.width()
            h = self.snackbar.height()
            self.snackbar.move(max(10, p_w - w - 20), max(10, p_h - h - 50))

    def closeEvent(self, event) -> None:
        if self.serial_worker:
            self.serial_worker.stop()
        if self.api_sync_worker and self.api_sync_worker.isRunning():
            self.api_sync_worker.quit()
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))
    win = MinimalFotaWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
