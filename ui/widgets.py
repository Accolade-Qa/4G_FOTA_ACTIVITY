"""Modular UI Custom Widgets & Workers.

Contains custom UI components:
- ApiSyncWorker: Asynchronous API background sync worker thread.
- CommandHistoryLineEdit: Serial AT command line input with Up/Down arrow history.
- InteractiveTerminalConsole: Monospace terminal output console with smart scroll.
- SnackbarWidget: Non-blocking floating toast notification banner.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

# Add repo root to Python path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QTextCursor, QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backend.orchestrator import FotaOrchestrator

logger = logging.getLogger(__name__)


class ApiSyncWorker(QThread):
    """Background thread for non-blocking REST API state matrix synchronization on startup."""

    sync_done_signal = pyqtSignal(bool, str)

    def __init__(self, orchestrator: FotaOrchestrator, parent=None) -> None:
        super().__init__(parent)
        self.orchestrator = orchestrator

    def run(self) -> None:
        """Run API sync in background without freezing main UI thread."""
        try:
            ok = self.orchestrator.initialize_system()
            msg = "API State Matrix Sync Complete." if ok else "Using cached state matrix."
            self.sync_done_signal.emit(ok, msg)
        except Exception as e:
            logger.warning("Background API sync exception: %s", e)
            self.sync_done_signal.emit(False, str(e))


class CommandHistoryLineEdit(QLineEdit):
    """QLineEdit supporting command history navigation via Up and Down arrow keys."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.history: List[str] = []
        self.history_idx: int = -1

    def record_command(self, cmd: str) -> None:
        """Add executed command string to history list."""
        if cmd and (not self.history or self.history[-1] != cmd):
            self.history.append(cmd)
        self.history_idx = len(self.history)

    def keyPressEvent(self, event) -> None:
        """Navigate command history with Up and Down arrow keys."""
        if event.key() == Qt.Key.Key_Up:
            if self.history and self.history_idx > 0:
                self.history_idx -= 1
                self.setText(self.history[self.history_idx])
            elif self.history and self.history_idx == -1:
                self.history_idx = len(self.history) - 1
                self.setText(self.history[self.history_idx])
            event.accept()
        elif event.key() == Qt.Key.Key_Down:
            if self.history and self.history_idx < len(self.history) - 1:
                self.history_idx += 1
                self.setText(self.history[self.history_idx])
            elif self.history_idx >= len(self.history) - 1:
                self.history_idx = len(self.history)
                self.clear()
            event.accept()
        else:
            super().keyPressEvent(event)


class InteractiveTerminalConsole(QPlainTextEdit):
    """Interactive Monospace Console supporting instant Space/Enter scroll-to-bottom and Copy/Paste."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("class", "light-console")
        self.setReadOnly(True)
        self.setMaximumBlockCount(3000)

    def keyPressEvent(self, event) -> None:
        """Handle key events: Pressing Enter or Space scrolls instantly to the bottom of the log."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.moveCursor(QTextCursor.MoveOperation.End)
            event.accept()
        else:
            super().keyPressEvent(event)


class SnackbarWidget(QFrame):
    """Compact Floating Toast/Snackbar Notification Banner."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("class", "snackbar")
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        self.lbl_text = QLabel("")
        self.lbl_text.setStyleSheet("color: #f8fafc; font-weight: 600; font-size: 8.5pt;")

        btn_close = QPushButton("✕")
        btn_close.setProperty("class", "snackbar-close")
        btn_close.setFixedWidth(16)
        btn_close.clicked.connect(self.hide)

        layout.addWidget(self.lbl_text)
        layout.addWidget(btn_close)

    def show_message(self, message: str, duration_ms: int = 3500) -> None:
        """Display small snackbar message and auto-hide without freezing main UI."""
        self.lbl_text.setText(message)
        self.adjustSize()

        if self.parent():
            p_w = self.parent().width()
            p_h = self.parent().height()
            w = self.width()
            h = self.height()
            x = p_w - w - 20
            y = p_h - h - 50
            self.move(max(10, x), max(10, y))

        self.show()
        self.raise_()
        QTimer.singleShot(duration_ms, self.hide)


class AuditHistoryTableWidget(QWidget):
    """Interactive Audit Results & FOTA History Viewer Tab with Filtering & Export."""

    def __init__(self, config, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.raw_records: List[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 1. Summary Stat Cards Panel
        stat_bar = QHBoxLayout()
        stat_bar.setSpacing(10)
        self.lbl_stat_total = self._create_card(stat_bar, "TOTAL EXECUTIONS", "0")
        self.lbl_stat_success = self._create_card(stat_bar, "COMPLETED", "0")
        self.lbl_stat_aborted = self._create_card(stat_bar, "ABORTED / FAILED", "0")
        self.lbl_stat_rate = self._create_card(stat_bar, "SUCCESS RATE", "0.0%")
        layout.addLayout(stat_bar)

        # 2. Filter & Control Header Bar
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(8)

        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("🔍 Filter by UIN, IMEI, VIN, Version...")
        self.input_search.textChanged.connect(self._apply_filters)

        self.combo_status_filter = QComboBox()
        self.combo_status_filter.addItems(["All Statuses", "COMPLETED", "ABORTED", "IN_PROGRESS", "BLOCKED"])
        self.combo_status_filter.currentTextChanged.connect(self._apply_filters)

        btn_refresh = QPushButton("↻ Refresh")
        btn_refresh.setFixedWidth(90)
        btn_refresh.clicked.connect(self.load_history)

        btn_export = QPushButton("📥 Export CSV")
        btn_export.setProperty("class", "btn-primary")
        btn_export.setFixedWidth(110)
        btn_export.clicked.connect(self._export_csv)

        ctrl_bar.addWidget(self.input_search, stretch=1)
        ctrl_bar.addWidget(self.combo_status_filter)
        ctrl_bar.addWidget(btn_refresh)
        ctrl_bar.addWidget(btn_export)
        layout.addLayout(ctrl_bar)

        # 3. Audit History Data Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Timestamp", "UIN", "IMEI", "VIN", "Initial Ver", "Target Ver", "State", "Status", "Remarks"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.load_history()

    def _create_card(self, parent_layout: QHBoxLayout, title: str, default: str) -> QLabel:
        """Create a styled metric card for audit statistics."""
        card = QFrame()
        card.setProperty("class", "metric-card")
        card_box = QVBoxLayout(card)
        card_box.setContentsMargins(10, 6, 10, 6)
        card_box.setSpacing(2)

        lbl_t = QLabel(title)
        lbl_t.setProperty("class", "stat-label")
        lbl_v = QLabel(default)
        lbl_v.setProperty("class", "stat-value")
        lbl_v.setStyleSheet("font-size: 11pt; font-weight: 800;")
        card_box.addWidget(lbl_t)
        card_box.addWidget(lbl_v)
        parent_layout.addWidget(card)
        return lbl_v

    def load_history(self) -> None:
        """Load and display audit records from results/fota_results.json."""
        json_path = self.config.results_dir / "fota_results.json"
        self.raw_records = []
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    self.raw_records = json.load(f)
            except Exception as e:
                logger.warning("Error loading audit history json: %s", e)

        if not isinstance(self.raw_records, list):
            self.raw_records = []

        # Update metrics
        total = len(self.raw_records)
        completed = sum(1 for r in self.raw_records if isinstance(r, dict) and "COMPLETED" in str(r.get("status", "")).upper())
        aborted = sum(1 for r in self.raw_records if isinstance(r, dict) and ("ABORTED" in str(r.get("status", "")).upper() or "FAILED" in str(r.get("status", "")).upper()))
        rate = (completed / total * 100.0) if total > 0 else 0.0

        self.lbl_stat_total.setText(str(total))
        self.lbl_stat_success.setText(str(completed))
        self.lbl_stat_aborted.setText(str(aborted))
        self.lbl_stat_rate.setText(f"{rate:.1f}%")

        self._apply_filters()

    def _apply_filters(self) -> None:
        """Filter table rows based on search text and status dropdown selection."""
        search_query = self.input_search.text().strip().lower() if hasattr(self, "input_search") else ""
        selected_status = self.combo_status_filter.currentText() if hasattr(self, "combo_status_filter") else "All Statuses"

        self.table.setRowCount(0)
        row_idx = 0
        for r in reversed(self.raw_records):
            if not isinstance(r, dict):
                continue

            st_val = str(r.get("status", "")).upper()
            if selected_status != "All Statuses" and selected_status not in st_val:
                continue

            row_str = f"{r.get('timestamp','')} {r.get('uin','')} {r.get('imei','')} {r.get('vin','')} {r.get('initialVersion','')} {r.get('targetVersion','')} {r.get('state','')} {st_val} {r.get('remarks','')}".lower()
            if search_query and search_query not in row_str:
                continue

            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(r.get("timestamp", ""))))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(r.get("uin", ""))))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(r.get("imei", ""))))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(r.get("vin", ""))))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(r.get("initialVersion", ""))))
            self.table.setItem(row_idx, 5, QTableWidgetItem(str(r.get("targetVersion", ""))))
            self.table.setItem(row_idx, 6, QTableWidgetItem(str(r.get("state", ""))))

            st_item = QTableWidgetItem(st_val)
            if "COMPLETED" in st_val:
                st_item.setForeground(QColor("#16a34a"))
            elif "ABORTED" in st_val or "FAILED" in st_val:
                st_item.setForeground(QColor("#dc2626"))
            elif "IN_PROGRESS" in st_val or "PROGRESS" in st_val:
                st_item.setForeground(QColor("#d97706"))
            else:
                st_item.setForeground(QColor("#d97706"))

            self.table.setItem(row_idx, 7, st_item)
            self.table.setItem(row_idx, 8, QTableWidgetItem(str(r.get("remarks", ""))))
            row_idx += 1

    def _export_csv(self) -> None:
        """Export current filtered table to CSV file."""
        dest_path, _ = QFileDialog.getSaveFileName(self, "Export FOTA Audit Report", "fota_audit_report.csv", "CSV Files (*.csv)")
        if dest_path:
            try:
                import csv
                with open(dest_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Timestamp", "UIN", "IMEI", "VIN", "InitialVersion", "TargetVersion", "State", "Status", "Remarks"])
                    for row in range(self.table.rowCount()):
                        row_data = [self.table.item(row, col).text() if self.table.item(row, col) else "" for col in range(9)]
                        writer.writerow(row_data)
                logger.info("Exported audit report to: %s", dest_path)
            except Exception as e:
                logger.error("Failed to export CSV: %s", e)


class ConsoleTabWidget(QWidget):
    """Dedicated Live Serial Console & Real-time Debugger Tab."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Controls Header
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(8)

        self.input_filter = QLineEdit()
        self.input_filter.setPlaceholderText("🔍 Filter live serial logs (e.g. ACON, UFW, CIP2, SLEEP)...")
        self.input_filter.textChanged.connect(self._filter_logs)

        self.btn_pause = QPushButton("⏸ Pause Scroll")
        self.btn_pause.setFixedWidth(110)
        self.btn_pause.setCheckable(True)

        self.btn_clear = QPushButton("🗑 Clear")
        self.btn_clear.setFixedWidth(80)

        self.btn_save = QPushButton("💾 Save Log")
        self.btn_save.setProperty("class", "btn-secondary")
        self.btn_save.setFixedWidth(95)
        self.btn_save.clicked.connect(self._save_log_file)

        ctrl_bar.addWidget(self.input_filter, stretch=1)
        ctrl_bar.addWidget(self.btn_pause)
        ctrl_bar.addWidget(self.btn_clear)
        ctrl_bar.addWidget(self.btn_save)
        layout.addLayout(ctrl_bar)

        # Monospace Console Widget
        self.console = InteractiveTerminalConsole()
        self.btn_clear.clicked.connect(self.console.clear)
        layout.addWidget(self.console, stretch=1)

        self._all_lines: List[str] = []

    def append_log_line(self, line: str) -> None:
        """Append log line to in-memory history and display if passes active filter."""
        self._all_lines.append(line)
        if len(self._all_lines) > 5000:
            self._all_lines = self._all_lines[-3000:]

        filter_text = self.input_filter.text().strip().lower()
        if not filter_text or filter_text in line.lower():
            self.console.appendPlainText(line)
            if not self.btn_pause.isChecked():
                sb = self.console.verticalScrollBar()
                sb.setValue(sb.maximum())

    def _filter_logs(self, query: str) -> None:
        """Re-populate console based on search filter query."""
        self.console.clear()
        query_clean = query.strip().lower()
        matching = [l for l in self._all_lines if not query_clean or query_clean in l.lower()]
        self.console.setPlainText("\n".join(matching))
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _save_log_file(self) -> None:
        """Save captured console logs to external text file."""
        dest_path, _ = QFileDialog.getSaveFileName(self, "Save Serial Log File", "device_serial_log.txt", "Text Files (*.txt);;All Files (*)")
        if dest_path:
            try:
                with open(dest_path, "w", encoding="utf-8") as f:
                    f.write(self.console.toPlainText())
                logger.info("Saved console log to: %s", dest_path)
            except Exception as e:
                logger.error("Failed to save log file: %s", e)


class ReportingAnalyticsTabWidget(QWidget):
    """Executive Analytics & Deep Insights Reporting Dashboard Tab."""

    def __init__(self, config, parent=None) -> None:
        super().__init__(parent)
        self.config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header controls inside tab
        ctrl_bar = QHBoxLayout()
        title = QLabel("📈 FOTA System Executive Analytics & Distribution Report")
        title.setStyleSheet("font-weight: 700; font-size: 10pt;")

        btn_refresh = QPushButton("↻ Refresh Analytics")
        btn_refresh.setFixedWidth(140)
        btn_refresh.clicked.connect(self.load_analytics)

        ctrl_bar.addWidget(title)
        ctrl_bar.addStretch()
        ctrl_bar.addWidget(btn_refresh)
        layout.addLayout(ctrl_bar)

        # Splitter Layout for State Matrix & Firmware Distribution Tables
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Table 1: State Server Execution Summary
        grp_state = QGroupBox("📍 State Server Execution Matrix Distribution")
        layout_s = QVBoxLayout(grp_state)
        self.table_states = QTableWidget()
        self.table_states.setColumnCount(4)
        self.table_states.setHorizontalHeaderLabels(["State Name", "Total Tests", "Completed", "Pass Rate"])
        self.table_states.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout_s.addWidget(self.table_states)
        splitter.addWidget(grp_state)

        # Table 2: Version Progression Summary
        grp_ver = QGroupBox("⚙️ Firmware Version Progression Breakdown")
        layout_v = QVBoxLayout(grp_ver)
        self.table_versions = QTableWidget()
        self.table_versions.setColumnCount(4)
        self.table_versions.setHorizontalHeaderLabels(["Initial Version", "Target Version", "Attempts", "Status"])
        self.table_versions.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout_v.addWidget(self.table_versions)
        splitter.addWidget(grp_ver)

        layout.addWidget(splitter, stretch=1)
        self.load_analytics()

    def load_analytics(self) -> None:
        """Calculate state matrix and version progression distribution from audit logs."""
        json_path = self.config.results_dir / "fota_results.json"
        records = []
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception as e:
                logger.warning("Error loading analytics json: %s", e)

        if not isinstance(records, list):
            records = []

        # Process state stats
        state_counts = {}
        for r in records:
            if isinstance(r, dict):
                st = str(r.get("state", "Unknown"))
                status = str(r.get("status", "")).upper()
                if st not in state_counts:
                    state_counts[st] = {"total": 0, "completed": 0}
                state_counts[st]["total"] += 1
                if "COMPLETED" in status:
                    state_counts[st]["completed"] += 1

        self.table_states.setRowCount(0)
        for idx, (st, data) in enumerate(state_counts.items()):
            self.table_states.insertRow(idx)
            self.table_states.setItem(idx, 0, QTableWidgetItem(st))
            self.table_states.setItem(idx, 1, QTableWidgetItem(str(data["total"])))
            self.table_states.setItem(idx, 2, QTableWidgetItem(str(data["completed"])))
            rate = (data["completed"] / data["total"] * 100) if data["total"] > 0 else 0
            self.table_states.setItem(idx, 3, QTableWidgetItem(f"{rate:.1f}%"))

        # Process version stats
        self.table_versions.setRowCount(0)
        for idx, r in enumerate(reversed(records)):
            if not isinstance(r, dict):
                continue
            self.table_versions.insertRow(idx)
            self.table_versions.setItem(idx, 0, QTableWidgetItem(str(r.get("initialVersion", "---"))))
            self.table_versions.setItem(idx, 1, QTableWidgetItem(str(r.get("targetVersion", "---"))))
            self.table_versions.setItem(idx, 2, QTableWidgetItem(str(r.get("attemptCount", "1"))))
            st_val = str(r.get("status", "")).upper()
            self.table_versions.setItem(idx, 3, QTableWidgetItem(st_val))


class StageProgressionWidget(QFrame):
    """Dedicated 10-Stage Progression Bar Widget displaying live FOTA stage status."""

    STAGE_NAMES = [
        "S1: Telemetry Params",
        "S2: Servers Matrix",
        "S3: Progress Sync",
        "S4: Audit Report",
        "S5: 100% Downloaded",
        "S6: Device Reboot",
        "S7: IP1 & Port Set",
        "S8: IP2 & Port Set",
        "S9: State OTA Fired",
        "S10: Config Verified"
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("StageProgressionWidget")
        self.setStyleSheet("""
            QFrame#StageProgressionWidget {
                background-color: #0b0f19;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 4px;
            }
            QLabel {
                font-size: 7.5pt;
                font-weight: 600;
                border-radius: 4px;
                padding: 4px 2px;
            }
            QLabel[class~="stage-waiting"] {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
            }
            QLabel[class~="stage-running"] {
                background-color: #78350f;
                color: #fef08a;
                border: 1px solid #d97706;
            }
            QLabel[class~="stage-passed"] {
                background-color: #064e3b;
                color: #a7f3d0;
                border: 1px solid #16a34a;
            }
            QLabel[class~="stage-failed"] {
                background-color: #7f1d1d;
                color: #fecaca;
                border: 1px solid #dc2626;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.stage_labels: List[QLabel] = []
        for idx, name in enumerate(self.STAGE_NAMES, 1):
            lbl = QLabel(f"{name}\n⏱ WAITING")
            lbl.setProperty("class", "stage-waiting")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl, stretch=1)
            self.stage_labels.append(lbl)

    def reset_stages(self) -> None:
        """Reset all 10 stages back to WAITING state."""
        for idx, name in enumerate(self.STAGE_NAMES, 1):
            lbl = self.stage_labels[idx - 1]
            lbl.setText(f"{name}\n⏱ WAITING")
            lbl.setProperty("class", "stage-waiting")
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

    def update_stage(self, stage_num: int, status: str, message: str = "") -> None:
        """Update a specific stage status (1 to 10) with 'WAITING', 'RUNNING', 'PASSED', or 'FAILED'."""
        if not (1 <= stage_num <= 10):
            return

        lbl = self.stage_labels[stage_num - 1]
        name = self.STAGE_NAMES[stage_num - 1]
        status_clean = str(status).upper()

        badge_class = "stage-waiting"
        icon = "⏱"
        if status_clean in ("RUNNING", "IN_PROGRESS"):
            badge_class = "stage-running"
            icon = "⚡"
        elif status_clean in ("PASSED", "COMPLETED", "OK"):
            badge_class = "stage-passed"
            icon = "✓"
        elif status_clean in ("FAILED", "ABORTED", "ERROR"):
            badge_class = "stage-failed"
            icon = "✕"

        detail = f"\n{icon} {status_clean}"
        lbl.setText(f"{name}{detail}")
        lbl.setProperty("class", badge_class)
        lbl.style().unpolish(lbl)
        lbl.style().polish(lbl)
