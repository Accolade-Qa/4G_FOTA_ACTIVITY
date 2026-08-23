"""Minimalist Desktop UI Interface Main Window Controller.

Provides light theme styling, interactive serial AT command sending with Up/Down arrow history,
smart auto-scroll, state selection dropdown, and automated CIP2 QA server verification and reboot handling.
Imports modular UI widgets from ui.widgets.
"""

import re
import datetime
import json
import sys
import logging
from pathlib import Path
from typing import Optional, List

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# Add repo root to Python path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.path_resolver import get_base_dir
from backend.config import Config
from backend.models import LoginPacketInfo
from backend.orchestrator import FotaOrchestrator
from backend.serial_worker import SerialWorker
from backend.message_parser import MessageParser
from backend.session_logger import SessionLogger
from ui.styles import LIGHT_THEME_QSS, DARK_THEME_QSS
from ui.widgets import (
    ApiSyncWorker,
    AuditHistoryTableWidget,
    CommandHistoryLineEdit,
    ConsoleTabWidget,
    InteractiveTerminalConsole,
    LoginPacketsTableWidget,
    ReportingAnalyticsTabWidget,
    SnackbarWidget,
    StageProgressionWidget,
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

        self.config = Config(get_base_dir())
        self.session_logger = SessionLogger(self.config.logs_dir)
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
        """Build clean 10/10 Industry Standard interface layout with tabs, progress bar, shortcuts, and audit viewer."""
        root = QWidget(self)
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

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
        self.btn_refresh.setToolTip("Refresh COM ports (Ctrl+R)")
        self.btn_refresh.clicked.connect(self._refresh_ports)

        self.btn_theme = QPushButton("🌙")
        self.btn_theme.setProperty("class", "btn-icon")
        self.btn_theme.setFixedWidth(32)
        self.btn_theme.setToolTip("Toggle Dark / Light Theme (Ctrl+T)")
        self.btn_theme.clicked.connect(self._toggle_theme)

        self.btn_toggle = QPushButton("Start")
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

        # 2. Main Tab Widget Architecture
        self.tab_widget = QTabWidget()

        # --- TAB 1: Live Terminal Console & Engine Control ---
        tab_terminal = QWidget()
        term_layout = QVBoxLayout(tab_terminal)
        term_layout.setContentsMargins(8, 8, 8, 8)
        term_layout.setSpacing(8)

        # Captured Telemetry Bar
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

        term_layout.addWidget(tel_bar)

        # Visual Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 10000)  # Enables 2-decimal places (0-100.00%)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("FOTA Download Progress: 0.00%")
        term_layout.addWidget(self.progress_bar)

        # 10-Stage Progression Bar Widget
        self.stage_widget = StageProgressionWidget()
        term_layout.addWidget(self.stage_widget)

        # Enterprise Status Banner Card
        self.frame_msg_card = QFrame()
        self.frame_msg_card.setProperty("class", "status-banner status-banner-info")
        msg_box = QHBoxLayout(self.frame_msg_card)
        msg_box.setContentsMargins(10, 4, 10, 4)
        msg_box.setSpacing(8)

        self.lbl_stage_badge = QLabel("READY")
        self.lbl_stage_badge.setStyleSheet("font-weight: 800; font-size: 8.5pt; color: #2563eb;")

        self.lbl_msg = QLabel("Connect device serial COM port and click Start Engine to initiate FOTA monitoring.")
        self.lbl_msg.setStyleSheet("font-size: 9pt; font-weight: 600;")
        self.lbl_msg.setWordWrap(True)

        msg_box.addWidget(self.lbl_stage_badge)
        msg_box.addWidget(QLabel("|"))
        msg_box.addWidget(self.lbl_msg, stretch=1)
        term_layout.addWidget(self.frame_msg_card)

        # Interactive Log Terminal Console
        self.console = InteractiveTerminalConsole()
        term_layout.addWidget(self.console, stretch=1)

        # Command Input Bar
        cmd_box = QHBoxLayout()
        self.input_cmd = CommandHistoryLineEdit()
        self.input_cmd.setPlaceholderText("Type serial/AT command and press Enter (e.g. *SET#CRST#1#)... Use Up/Down arrow for history.")
        self.input_cmd.returnPressed.connect(self._on_send_command)

        self.btn_send_cmd = QPushButton("Send Command")
        self.btn_send_cmd.setFixedWidth(120)
        self.btn_send_cmd.clicked.connect(self._on_send_command)

        self.btn_clear_log = QPushButton("Clear Log")
        self.btn_clear_log.setProperty("class", "btn-secondary")
        self.btn_clear_log.setFixedWidth(90)
        self.btn_clear_log.setToolTip("Clear terminal console (Ctrl+K / Ctrl+L)")
        self.btn_clear_log.clicked.connect(self.console.clear)

        cmd_box.addWidget(self.input_cmd, stretch=1)
        cmd_box.addWidget(self.btn_send_cmd)
        cmd_box.addWidget(self.btn_clear_log)
        term_layout.addLayout(cmd_box)

        self.tab_widget.addTab(tab_terminal, "🖥️ Live Serial Console & Control")

        # --- TAB 2: Execution Audit Log History ---
        self.audit_tab = AuditHistoryTableWidget(self.config)
        self.tab_widget.addTab(self.audit_tab, "📊 Audit Log History")

        # --- TAB 3: Executive Analytics & Deep Insights ---
        self.analytics_tab = ReportingAnalyticsTabWidget(self.config)
        self.tab_widget.addTab(self.analytics_tab, "📈 Analytics & Reporting")

        # --- TAB 4: Received Login Packets History ---
        self.login_packets_tab = LoginPacketsTableWidget()
        self.tab_widget.addTab(self.login_packets_tab, "📦 Login Packets")

        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tab_widget, stretch=1)

        # Global Keyboard Shortcuts
        self._setup_shortcuts()

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts for fast engineering workflows."""
        sc_clear = QShortcut(QKeySequence("Ctrl+K"), self)
        sc_clear.activated.connect(self.console.clear)

        sc_clear2 = QShortcut(QKeySequence("Ctrl+L"), self)
        sc_clear2.activated.connect(self.console.clear)

        sc_refresh = QShortcut(QKeySequence("Ctrl+R"), self)
        sc_refresh.activated.connect(self._refresh_ports)

        sc_theme = QShortcut(QKeySequence("Ctrl+T"), self)
        sc_theme.activated.connect(self._toggle_theme)

        sc_esc = QShortcut(QKeySequence("Esc"), self)
        sc_esc.activated.connect(self.input_cmd.clear)

    @pyqtSlot(int)
    def _on_tab_changed(self, idx: int) -> None:
        """Refresh audit table or analytics dashboard when switching tabs."""
        if idx == 1 and hasattr(self, "audit_tab"):
            self.audit_tab.load_history()
        elif idx == 2 and hasattr(self, "analytics_tab"):
            self.analytics_tab.load_analytics()

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
        self.orchestrator.status_signal.connect(self._on_orchestrator_status_update)
        self.orchestrator.device_info_signal.connect(self._on_device_info)
        self.orchestrator.progress_signal.connect(self._on_progress_update)
        self.orchestrator.request_command_signal.connect(self._auto_execute_command)
        self.orchestrator.snackbar_signal.connect(self._show_snackbar_toast)
        self.orchestrator.stage_signal.connect(self.stage_widget.update_stage)

    @pyqtSlot(str)
    def _show_snackbar_toast(self, msg: str) -> None:
        """Display non-blocking Snackbar Toast alert on UI."""
        if hasattr(self, "snackbar"):
            self.snackbar.show_message(msg, duration_ms=4500)

    @pyqtSlot(str)
    def _on_orchestrator_status_update(self, text: str) -> None:
        """Parse orchestrator status strings into dynamic, concise stage badges and cards."""
        if not text:
            return

        t_upper = text.upper()
        if "DOWNLOADING" in t_upper or "IN-PROGRESS" in t_upper or "PROGRESS:" in t_upper:
            self._update_status_card("⚡ IN-PROGRESS", text, level="info")
        elif "COMPLETED" in t_upper or "ACCEPTED" in t_upper or "SUCCESS" in t_upper:
            self._update_status_card("🎉 COMPLETED", text, level="success")
        elif "ABORTED" in t_upper or "FAILED" in t_upper or "CANCELLED" in t_upper:
            self._update_status_card("⛔ ABORTED", text, level="danger")
        elif "BLOCKED" in t_upper or "NOT FOUND" in t_upper or "WARNING" in t_upper:
            self._update_status_card("⚠️ WARNING", text, level="warning")
        elif "SCANNING" in t_upper or "FETCHING" in t_upper:
            self._update_status_card("📋 SCANNING", text, level="info")
        else:
            self._update_status_card("ℹ️ STATUS", text, level="info")

    def _update_status_card(self, badge: str, message: str, level: str = "info") -> None:
        """Update status card badge text, message detail, and QSS class dynamically."""
        self.lbl_stage_badge.setText(badge)
        self.lbl_msg.setText(message)

        color_map = {
            "info": "#2563eb",
            "success": "#16a34a",
            "warning": "#d97706",
            "danger": "#dc2626"
        }
        badge_color = color_map.get(level, "#2563eb")
        self.lbl_stage_badge.setStyleSheet(f"font-weight: 800; font-size: 8.5pt; color: {badge_color};")
        self.frame_msg_card.setProperty("class", f"status-banner status-banner-{level}")
        self.frame_msg_card.setStyle(self.frame_msg_card.style())

    @pyqtSlot(float)
    def _on_progress_update(self, val: float) -> None:
        """Handle download progress update with 2-decimal precision (e.g. 45.20%)."""
        val_clean = max(0.0, min(100.0, float(val)))
        self.progress_bar.setValue(int(val_clean * 100))
        self.progress_bar.setFormat(f"FOTA Download Progress: {val_clean:.2f}%")
        self._update_status_card("⚡ IN-PROGRESS", f"FOTA Downloading: {val_clean:.2f}%", level="info")

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
        self.serial_worker.sleep_event_signal.connect(self._on_sleep_event)
        self.serial_worker.port_status_signal.connect(self._on_port_status)
        self.serial_worker.start()

        # Update UI Controls to ONLINE & Stop Engine
        self.combo_ports.setEnabled(False)
        self.btn_refresh.setEnabled(False)

        self.lbl_status.setText(f"● ONLINE ({port} @ {self.config.serial_baud})")
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

    @pyqtSlot(str)
    def _on_sleep_event(self, log_line: str) -> None:
        """Handle device sleep and soft shutdown detection signals."""
        msg = "Soft shutdown detected. Monitoring for wake-up boot log..."
        self._update_status_card("🌙 DEVICE SLEEP", msg, level="warning")
        self.snackbar.show_message("🌙 Device Sleep / Soft Shutdown Detected!", duration_ms=4000)

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

        # Update session logger filename pattern: {IMEI}_{REL_FETCHED}_TO_{REL_UPDATE}.log
        if info.imei or info.version or self.orchestrator.target_version:
            self.session_logger.update_session_info(
                info.imei,
                info.version,
                self.orchestrator.target_version
            )

        # Trigger Snackbar ONLY ONCE when a new UIN is detected (prevents UI freeze)
        toast_key = (info.uin, info.imei)
        if info.uin and toast_key != self._last_toast_key:
            self._last_toast_key = toast_key
            toast_text = f"⚡ Device Detected: UIN {info.uin} | IMEI {info.imei}"
            self.snackbar.show_message(toast_text, duration_ms=3000)

    def _queue_log_line(self, line: str) -> None:
        """Queue incoming serial line for batch flushing, inspect for login packets, CIP2 server verification, and parse real-time progress."""
        self._log_buffer.append(line)

        # Inspect for Login Packet in raw line (e.g. 55AA or Key-Value login packet)
        pkt = MessageParser.parse_login_packet(line)
        if pkt and hasattr(self, "login_packets_tab"):
            self.login_packets_tab.add_login_packet(pkt, line)

        tot_size = self.orchestrator.total_fota_file_size if self.orchestrator else 0
        prog = MessageParser.parse_download_progress(line, total_file_size=tot_size)
        if prog is not None and self.orchestrator:
            self.orchestrator.update_progress(prog)
        if self.orchestrator:
            self.orchestrator.process_log_line(line)

    def _flush_log_buffer(self) -> None:
        """Flush queued log lines without moving viewport and delegate logging to SessionLogger."""
        if self._log_buffer:
            sb = self.console.verticalScrollBar()
            prev_val = sb.value()
            max_val = sb.maximum()

            at_bottom = prev_val >= (max_val - 25)

            # Delegate writing formatted millisecond timestamp logs to SessionLogger
            if hasattr(self, "session_logger"):
                if self.orchestrator and self.orchestrator.current_device:
                    dev = self.orchestrator.current_device
                    self.session_logger.update_session_info(dev.imei, dev.version, self.orchestrator.target_version)
                self.session_logger.write_lines(self._log_buffer)

            lines = "\n".join(self._log_buffer)
            self._log_buffer.clear()

            self.console.appendPlainText(lines)

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
