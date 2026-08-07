"""Modular UI Custom Widgets & Workers.

Contains custom UI components:
- ApiSyncWorker: Asynchronous API background sync worker thread.
- CommandHistoryLineEdit: Serial AT command line input with Up/Down arrow history.
- InteractiveTerminalConsole: Monospace terminal output console with smart scroll.
- SnackbarWidget: Non-blocking floating toast notification banner.
"""

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
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
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
