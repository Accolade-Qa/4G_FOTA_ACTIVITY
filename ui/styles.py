"""Clean & Professional Light Theme Stylesheet.

Provides high-contrast, elegant light theme QSS styling for PyQt6 components.
Uses explicit point size (pt) typography to prevent DPI font scaling warnings.
"""

LIGHT_THEME_QSS = """
QMainWindow {
    background-color: #f8fafc;
}

QWidget {
    font-family: "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
    font-size: 9pt;
    color: #1e293b;
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
    color: #2563eb;
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
    background-color: #f1f5f9;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 9pt;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #e2e8f0;
    color: #0f172a;
}

QPushButton.btn-primary {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
}

QPushButton.btn-primary:hover {
    background-color: #1d4ed8;
}

QPushButton.btn-danger {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
}

QPushButton.btn-danger:hover {
    background-color: #b91c1c;
}

QPushButton.btn-icon {
    background-color: #ffffff;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 10pt;
    font-weight: bold;
}

QPushButton.btn-icon:hover {
    background-color: #f1f5f9;
    color: #2563eb;
    border-color: #2563eb;
}

QPushButton.btn-secondary {
    background-color: #ffffff;
    color: #64748b;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 8.5pt;
    font-weight: 600;
}

QPushButton.btn-secondary:hover {
    background-color: #f1f5f9;
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
    background-color: #e2e8f0;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    height: 16px;
    text-align: center;
    font-size: 8.5pt;
    font-weight: 700;
    color: #0f172a;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4fd622, stop:1 #6cf53b);
    border-radius: 5px;
}

/* Light Tab Widget */
QTabWidget::pane {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background-color: #ffffff;
}

QTabBar::tab {
    background-color: #f1f5f9;
    color: #64748b;
    border: 1px solid #cbd5e1;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 16px;
    font-weight: 600;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #2563eb;
    border-color: #e2e8f0;
}

/* Light Audit Table */
QTableWidget {
    background-color: #ffffff;
    color: #0f172a;
    gridline-color: #e2e8f0;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    font-size: 9pt;
}

QHeaderView::section {
    background-color: #f1f5f9;
    color: #475569;
    font-weight: 700;
    padding: 6px;
    border: 1px solid #cbd5e1;
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
    background-color: #0b0f19;
}

QWidget {
    font-family: "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
    font-size: 9pt;
    color: #f1f5f9;
}

/* Header & Telemetry Card Containers */
QFrame.header-bar {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 8px 14px;
}

QFrame.telemetry-bar {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 8px 14px;
}

QLabel.app-title {
    font-weight: 800;
    font-size: 11.5pt;
    color: #38bdf8;
    letter-spacing: 1px;
}

/* Telemetry Stats */
QLabel.stat-label {
    font-size: 8pt;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.9px;
}

QLabel.stat-value {
    font-size: 9.5pt;
    font-weight: 700;
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
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 8px;
    padding: 10px 14px;
}

/* Buttons */
QPushButton {
    background-color: #1f2937;
    color: #f8fafc;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 9pt;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #374151;
    color: #ffffff;
    border-color: #4b5563;
}

QPushButton.btn-primary {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #2563eb);
    color: #ffffff;
    border: none;
    font-weight: 700;
}

QPushButton.btn-primary:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #3b82f6);
}

QPushButton.btn-danger {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e11d48, stop:1 #f43f5e);
    color: #ffffff;
    border: none;
    font-weight: 700;
}

QPushButton.btn-danger:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f43f5e, stop:1 #fb7185);
}

QPushButton.btn-icon {
    background-color: #111827;
    color: #cbd5e1;
    border: 1px solid #1f2937;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 10pt;
    font-weight: bold;
}

QPushButton.btn-icon:hover {
    background-color: #1f2937;
    color: #38bdf8;
    border-color: #38bdf8;
}

QPushButton.btn-secondary {
    background-color: #111827;
    color: #94a3b8;
    border: 1px solid #1f2937;
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 8.5pt;
    font-weight: 600;
}

QPushButton.btn-secondary:hover {
    background-color: #1f2937;
    color: #38bdf8;
    border-color: #38bdf8;
}

/* Status Badges */
QLabel.status-online {
    color: #10b981;
    font-weight: 800;
    font-size: 9pt;
}

QLabel.status-offline {
    color: #f43f5e;
    font-weight: 800;
    font-size: 9pt;
}

QLabel.status-syncing {
    color: #f59e0b;
    font-weight: 800;
    font-size: 9pt;
}

/* Inputs & Combo Box */
QComboBox, QLineEdit {
    background-color: #111827;
    color: #f8fafc;
    border: 1px solid #1f2937;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 9pt;
}

QComboBox:hover, QLineEdit:hover {
    border-color: #38bdf8;
}

QComboBox:focus, QLineEdit:focus {
    border-color: #0284c7;
}

QComboBox QAbstractItemView {
    background-color: #111827;
    color: #f8fafc;
    border: 1px solid #1f2937;
    selection-background-color: #1f2937;
    selection-color: #38bdf8;
}

QComboBox:disabled, QLineEdit:disabled {
    background-color: #0b0f19;
    color: #4b5563;
    border-color: #111827;
}

/* Electric Dark Progress Bar */
QProgressBar {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 6px;
    height: 16px;
    text-align: center;
    font-size: 8.5pt;
    font-weight: 700;
    color: #38bdf8;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:0.5 #38bdf8, stop:1 #818cf8);
    border-radius: 5px;
}

/* Dark Tab Widget */
QTabWidget::pane {
    border: 1px solid #1f2937;
    border-radius: 8px;
    background-color: #111827;
}

QTabBar::tab {
    background-color: #0b0f19;
    color: #94a3b8;
    border: 1px solid #1f2937;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 16px;
    font-weight: 600;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #111827;
    color: #38bdf8;
    border-color: #1f2937;
    border-top: 2px solid #38bdf8;
}

/* Dark Audit Table */
QTableWidget {
    background-color: #030712;
    color: #f8fafc;
    gridline-color: #1f2937;
    border: 1px solid #1f2937;
    border-radius: 8px;
    font-size: 9pt;
}

QHeaderView::section {
    background-color: #111827;
    color: #38bdf8;
    font-weight: 700;
    padding: 6px;
    border: 1px solid #1f2937;
}

/* Dark Monospace Terminal Console */
QPlainTextEdit.light-console {
    background-color: #030712;
    color: #f8fafc;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 9.5pt;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 8px;
}

/* Toast / Snackbar Notification */
QFrame.snackbar {
    background-color: #111827;
    border: 1px solid #38bdf8;
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

/* Scrollbars */
QScrollBar:vertical {
    background: #0b0f19;
    width: 8px;
}

QScrollBar::handle:vertical {
    background: #1f2937;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #374151;
}
"""
