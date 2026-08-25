"""Clean & Refined Professional Theme Stylesheets.

Provides high-contrast, elegant Light and Dark theme QSS styling for PyQt6 components.
Uses explicit point size (pt) typography to prevent DPI font scaling warnings.
"""

LIGHT_THEME_QSS = """
QMainWindow {
    background-color: #f8fafc;
}

QWidget {
    font-family: "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
    font-size: 9pt;
    color: #0f172a;
}

/* Header & Telemetry Card Containers */
QFrame.header-bar {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 8px 14px;
}

QFrame.telemetry-bar {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 8px 14px;
}

QLabel.app-title {
    font-weight: 700;
    font-size: 11pt;
    color: #0f172a;
    letter-spacing: 0.5px;
}

/* Telemetry Stats */
QLabel.stat-label {
    font-size: 8pt;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}

QLabel.stat-value {
    font-size: 9.5pt;
    font-weight: 600;
    color: #0f172a;
    border: none;
    background-color: transparent;
}

/* Status Banner Cards */
QFrame.status-banner {
    border-radius: 8px;
    padding: 6px 12px;
}

QFrame.status-banner-info {
    background-color: #eff6ff;
    border: 1px solid #bfdbfe;
}

QFrame.status-banner-success {
    background-color: #f0fdf4;
    border: 1px solid #bbf7d0;
}

QFrame.status-banner-warning {
    background-color: #fffbeb;
    border: 1px solid #fde68a;
}

QFrame.status-banner-danger {
    background-color: #fef2f2;
    border: 1px solid #fecaca;
}

/* Reporting Stat Cards */
QFrame.metric-card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px 14px;
}

/* Light Theme Buttons */
QPushButton {
    background-color: #ffffff;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 9pt;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #f1f5f9;
    color: #0f172a;
    border-color: #94a3b8;
}

QPushButton.btn-primary {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #1d4ed8;
}

QPushButton.btn-primary:hover {
    background-color: #1d4ed8;
    color: #ffffff;
}

QPushButton.btn-danger {
    background-color: #dc2626;
    color: #ffffff;
    border: 1px solid #b91c1c;
}

QPushButton.btn-danger:hover {
    background-color: #b91c1c;
    color: #ffffff;
}

QPushButton.btn-secondary {
    background-color: #ffffff;
    color: #475569;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 8.5pt;
    font-weight: 600;
}

QPushButton.btn-secondary:hover {
    background-color: #f8fafc;
    color: #0f172a;
    border-color: #94a3b8;
}

/* Status Badges */
QLabel.status-online {
    color: #16a34a;
    font-weight: 700;
    font-size: 9pt;
}

QLabel.status-offline {
    color: #dc2626;
    font-weight: 700;
    font-size: 9pt;
}

/* Inputs & Combo Box */
QComboBox, QLineEdit {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 9pt;
}

QComboBox:hover, QLineEdit:hover {
    border-color: #2563eb;
}

QComboBox:disabled, QLineEdit:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border-color: #e2e8f0;
}

/* Modern Light Progress Bar */
QProgressBar {
    background-color: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    height: 16px;
    text-align: center;
    font-size: 8.5pt;
    font-weight: 700;
    color: #0f172a;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16a34a, stop:1 #4ade80);
    border-radius: 5px;
}

/* Light Tab Widget */
QTabWidget::pane {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background-color: #ffffff;
}

QTabBar::tab {
    background-color: #f8fafc;
    color: #64748b;
    border: 1px solid #e2e8f0;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 16px;
    font-weight: 600;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #0f172a;
    border-color: #e2e8f0;
    border-top: 3px solid #2563eb;
}

/* Light Audit Table */
QTableWidget {
    background-color: #ffffff;
    color: #0f172a;
    gridline-color: #f1f5f9;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    font-size: 9pt;
    selection-background-color: #dbeafe;
    selection-color: #1e40af;
}

QTableWidget::item:hover {
    background-color: #eff6ff;
    color: #1e40af;
}

QTableWidget::item:selected {
    background-color: #dbeafe;
    color: #1e40af;
}

QHeaderView::section {
    background-color: #f8fafc;
    color: #475569;
    font-weight: 700;
    padding: 6px;
    border: 1px solid #e2e8f0;
}

/* Light Monospace Terminal Console */
QPlainTextEdit.light-console {
    background-color: #ffffff;
    color: #0f172a;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 9.5pt;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px;
}

/* Toast / Snackbar Notification */
QFrame.snackbar {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 14px;
}

QLabel.snackbar-text {
    color: #f8fafc;
    font-weight: 600;
    font-size: 9pt;
}

QPushButton.snackbar-close {
    background-color: transparent;
    color: #94a3b8;
    border: none;
    font-weight: 700;
    font-size: 11pt;
    padding: 0px 4px;
}

QPushButton.snackbar-close:hover {
    color: #ffffff;
}

/* Stage Progression Bar - Light Theme */
QFrame#StageProgressionWidget {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 4px;
}

QFrame#StageProgressionWidget QLabel {
    font-size: 7.5pt;
    font-weight: 600;
    border-radius: 4px;
    padding: 4px 2px;
}

QFrame#StageProgressionWidget QLabel[class~="stage-waiting"] {
    background-color: #f8fafc;
    color: #64748b;
    border: 1px solid #e2e8f0;
}

QFrame#StageProgressionWidget QLabel[class~="stage-running"] {
    background-color: #fef9c3;
    color: #854d0e;
    border: 1px solid #fde047;
}

QFrame#StageProgressionWidget QLabel[class~="stage-passed"] {
    background-color: #dcfce7;
    color: #15803d;
    border: 1px solid #86efac;
}

QFrame#StageProgressionWidget QLabel[class~="stage-failed"] {
    background-color: #fee2e2;
    color: #b91c1c;
    border: 1px solid #fca5a5;
}

/* Scrollbars */
QScrollBar:vertical {
    background: #f8fafc;
    width: 8px;
}

QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}
"""

DARK_THEME_QSS = """
QMainWindow {
    background-color: #0f172a;
}

QWidget {
    font-family: "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
    font-size: 9pt;
    color: #f8fafc;
}

/* Header & Telemetry Card Containers */
QFrame.header-bar {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 14px;
}

QFrame.telemetry-bar {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 14px;
}

QLabel.app-title {
    font-weight: 700;
    font-size: 11pt;
    color: #38bdf8;
    letter-spacing: 0.5px;
}

/* Telemetry Stats */
QLabel.stat-label {
    font-size: 8pt;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}

QLabel.stat-value {
    font-size: 9.5pt;
    font-weight: 600;
    color: #38bdf8;
    border: none;
    background-color: transparent;
}

/* Status Banner Cards */
QFrame.status-banner {
    border-radius: 8px;
    padding: 6px 12px;
}

QFrame.status-banner-info {
    background-color: #0f172a;
    border: 1px solid #1d4ed8;
}

QFrame.status-banner-success {
    background-color: #064e3b;
    border: 1px solid #10b981;
}

QFrame.status-banner-warning {
    background-color: #451a03;
    border: 1px solid #f59e0b;
}

QFrame.status-banner-danger {
    background-color: #4c0519;
    border: 1px solid #f43f5e;
}

/* Reporting Stat Cards */
QFrame.metric-card {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 10px 14px;
}

/* Buttons */
QPushButton {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 9pt;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #334155;
    color: #ffffff;
}

QPushButton.btn-primary {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #1d4ed8;
}

QPushButton.btn-primary:hover {
    background-color: #3b82f6;
    color: #ffffff;
}

QPushButton.btn-danger {
    background-color: #dc2626;
    color: #ffffff;
    border: 1px solid #b91c1c;
}

QPushButton.btn-danger:hover {
    background-color: #ef4444;
    color: #ffffff;
}

QPushButton.btn-secondary {
    background-color: #1e293b;
    color: #cbd5e1;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 8.5pt;
    font-weight: 600;
}

QPushButton.btn-secondary:hover {
    background-color: #334155;
    color: #ffffff;
}

/* Status Badges */
QLabel.status-online {
    color: #4ade80;
    font-weight: 700;
    font-size: 9pt;
}

QLabel.status-offline {
    color: #f87171;
    font-weight: 700;
    font-size: 9pt;
}

/* Inputs & Combo Box */
QComboBox, QLineEdit {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 9pt;
}

QComboBox:hover, QLineEdit:hover {
    border-color: #38bdf8;
}

QComboBox:disabled, QLineEdit:disabled {
    background-color: #1e293b;
    color: #64748b;
    border-color: #334155;
}

/* Dark Progress Bar */
QProgressBar {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    height: 18px;
    text-align: center;
    font-size: 8.5pt;
    font-weight: 800;
    color: #ffffff;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4ed8, stop:0.5 #2563eb, stop:1 #38bdf8);
    border-radius: 5px;
}

/* Dark Tab Widget */
QTabWidget::pane {
    border: 1px solid #334155;
    border-radius: 8px;
    background-color: #1e293b;
}

QTabBar::tab {
    background-color: #0f172a;
    color: #94a3b8;
    border: 1px solid #334155;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 16px;
    font-weight: 600;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #1e293b;
    color: #38bdf8;
    border-color: #334155;
    border-top: 3px solid #38bdf8;
}

/* Dark Audit Table */
QTableWidget {
    background-color: #0f172a;
    color: #f8fafc;
    gridline-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    font-size: 9pt;
    selection-background-color: #1e293b;
    selection-color: #38bdf8;
}

QTableWidget::item:hover {
    background-color: #1e293b;
    color: #38bdf8;
}

QTableWidget::item:selected {
    background-color: #334155;
    color: #f8fafc;
}

QHeaderView::section {
    background-color: #1e293b;
    color: #38bdf8;
    font-weight: 700;
    padding: 6px;
    border: 1px solid #334155;
}

/* Dark Monospace Terminal Console */
QPlainTextEdit.light-console {
    background-color: #090d16;
    color: #f8fafc;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 9.5pt;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px;
}

/* Stage Progression Bar - Dark Theme */
QFrame#StageProgressionWidget {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 4px;
}

QFrame#StageProgressionWidget QLabel {
    font-size: 7.5pt;
    font-weight: 600;
    border-radius: 4px;
    padding: 4px 2px;
}

QFrame#StageProgressionWidget QLabel[class~="stage-waiting"] {
    background-color: #0f172a;
    color: #94a3b8;
    border: 1px solid #334155;
}

QFrame#StageProgressionWidget QLabel[class~="stage-running"] {
    background-color: #451a03;
    color: #fde047;
    border: 1px solid #854d0e;
}

QFrame#StageProgressionWidget QLabel[class~="stage-passed"] {
    background-color: #064e3b;
    color: #86efac;
    border: 1px solid #10b981;
}

QFrame#StageProgressionWidget QLabel[class~="stage-failed"] {
    background-color: #4c0519;
    color: #fca5a5;
    border: 1px solid #f43f5e;
}

/* Scrollbars */
QScrollBar:vertical {
    background: #0f172a;
    width: 8px;
}

QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}
"""
