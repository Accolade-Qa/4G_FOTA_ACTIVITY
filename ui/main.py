import json
import os
import shutil
import sys
from pathlib import Path

from PyQt6.QtCore import QProcess, Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QFileDialog,
    QVBoxLayout,
    QWidget,
)


APP_TITLE = "FOTA Automation UI"
LAST_REPO_PATH_FILE = Path.home() / ".fota_ui_repo_root"
USER_DATA_DIR = Path.home() / ".fota_ui"


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _app_base_dir() -> Path:
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _resource_dir() -> Path:
    if _is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def _resource_path(rel_path: str) -> Path:
    return _resource_dir() / rel_path


ASSETS_DIR = _resource_path("assets")
LOGO_PATH = ASSETS_DIR / "logo.png"


def read_properties(path: Path) -> dict:
    data = {}
    if not path.exists():
        return data
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def write_properties(path: Path, data: dict) -> None:
    lines = [
        "# Serial configuration",
        f"serial.port={data.get('serial.port', '')}",
        f"serial.baud={data.get('serial.baud', '115200')}",
        "",
        "# Input/output paths",
        f"firmware.csv={data.get('firmware.csv', 'input/fota_batch.csv')}",
        f"audit.csv={data.get('audit.csv', 'results/fota_audit.csv')}",
        f"firmware.json={data.get('firmware.json', 'input/servers.json')}",
        f"login.json={data.get('login.json', 'results/login_packets.json')}",
        "",
        "# Portal credentials and URL",
        f"login.url={data.get('login.url', '')}",
        f"login.user={data.get('login.user', '')}",
        f"login.pass={data.get('login.pass', '')}",
        "",
        "# Device state (used as default if device reports 'Default')",
        f"state={data.get('state', 'Default')}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def find_jar(target_dir: Path) -> Path | None:
    if not target_dir.exists():
        return None
    jars = list(target_dir.glob("*.jar"))
    if not jars:
        return None
    preferred = [j for j in jars if "shaded" in j.name and "original" not in j.name]
    if preferred:
        return preferred[0]
    filtered = [j for j in jars if "original" not in j.name]
    return filtered[0] if filtered else None




class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))
        self.resize(980, 720)

        self.repo_root = self._resolve_repo_root()
        self._apply_repo_root(self.repo_root)

        self.backend_process: QProcess | None = None
        self.build_process: QProcess | None = None
        self.stop_requested = False

        self._init_ui()
        self._load_config()
        QTimer.singleShot(0, self._start_backend)

    def _apply_repo_root(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        if _is_frozen():
            USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
            self.config_path = USER_DATA_DIR / "config.properties"
            self.input_dir = USER_DATA_DIR / "input"
            self.results_dir = USER_DATA_DIR / "results"
            self.logs_dir = USER_DATA_DIR / "logs"
            self.output_dir = USER_DATA_DIR / "output"
            self.screenshots_dir = USER_DATA_DIR / "screenshots"
            for d in (
                self.input_dir,
                self.results_dir,
                self.logs_dir,
                self.output_dir,
                self.screenshots_dir,
            ):
                d.mkdir(parents=True, exist_ok=True)
            self.target_dir = _resource_path("backend")
            self._seed_default_inputs()
        else:
            self.config_path = repo_root / "config.properties"
            self.target_dir = repo_root / "target"
            self.input_dir = repo_root / "input"
            self.results_dir = repo_root / "results"
            self.logs_dir = repo_root / "logs"
            self.output_dir = repo_root / "output"
            self.screenshots_dir = repo_root / "screenshots"
        self.server_inputs_xlsx = self.input_dir / "Server_Inputs.xlsx"

    def _is_repo_root(self, path: Path) -> bool:
        if not path.exists() or not path.is_dir():
            return False
        # Require pom.xml to avoid mistaking the PyInstaller dist folder for repo root.
        return (path / "pom.xml").exists()

    def _resolve_repo_root(self) -> Path:
        if _is_frozen():
            # Standalone mode: use the app directory as root (backend JAR and runtime live here).
            return _app_base_dir()
        candidates: list[Path] = []
        if LAST_REPO_PATH_FILE.exists():
            try:
                saved = Path(LAST_REPO_PATH_FILE.read_text(encoding="utf-8").strip())
                if saved:
                    candidates.append(saved)
            except Exception:
                pass
        candidates.append(Path(__file__).resolve().parents[1])
        candidates.append(Path.cwd())

        for candidate in candidates:
            if self._is_repo_root(candidate):
                return candidate

        chosen = QFileDialog.getExistingDirectory(None, "Select FOTA repo folder", str(Path.cwd()))
        if chosen:
            chosen_path = Path(chosen)
            if self._is_repo_root(chosen_path):
                try:
                    LAST_REPO_PATH_FILE.write_text(str(chosen_path), encoding="utf-8")
                except Exception:
                    pass
                return chosen_path

        QMessageBox.warning(
            None,
            APP_TITLE,
            "Could not locate the repo root. Please select the folder that contains pom.xml.",
        )

        return Path(__file__).resolve().parents[1]

    def _seed_default_inputs(self) -> None:
        # Copy bundled defaults into user data dir if missing.
        defaults_dir = _resource_path("defaults")
        if not defaults_dir.exists():
            return
        for item in defaults_dir.iterdir():
            if not item.is_file():
                continue
            dest = self.input_dir / item.name
            if not dest.exists():
                try:
                    shutil.copy2(item, dest)
                except Exception:
                    pass

    def _init_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        form = QFormLayout()

        self.firmware_json_value = "input/servers.json"
        self.firmware_csv_value = "input/fota_batch.csv"
        self.audit_csv_value = "results/fota_audit.csv"
        self.login_json_value = "results/login_packets.json"

        self.portal_url = QLineEdit()
        form.addRow("Portal URL", self.portal_url)

        self.portal_user = QLineEdit()
        form.addRow("Portal User", self.portal_user)

        self.portal_pass = QLineEdit()
        self.portal_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Portal Pass", self.portal_pass)

        self.default_state = QLineEdit()
        form.addRow("Default State", self.default_state)

        layout.addLayout(form)

        button_row = QHBoxLayout()
        self.save_btn = QPushButton("Save Config")
        self.save_btn.clicked.connect(self._save_config)
        self.start_btn = QPushButton("Start Backend")
        self.start_btn.clicked.connect(self._start_backend)
        self.stop_btn = QPushButton("Stop Backend")
        self.stop_btn.clicked.connect(self._stop_backend)
        self.stop_btn.setEnabled(False)

        button_row.addWidget(self.save_btn)
        button_row.addWidget(self.start_btn)
        button_row.addWidget(self.stop_btn)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        layout.addWidget(QLabel("Backend Log"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, stretch=1)

        self.setCentralWidget(root)

    def _load_config(self) -> None:
        props = read_properties(self.config_path)
        def _get(key: str, default: str) -> str:
            value = props.get(key, "").strip()
            return value if value else default

        self.firmware_json_value = _get("firmware.json", "input/servers.json")
        self.firmware_csv_value = _get("firmware.csv", "input/fota_batch.csv")
        self.audit_csv_value = _get("audit.csv", "results/fota_audit.csv")
        self.login_json_value = _get("login.json", "results/login_packets.json")
        self.portal_url.setText(props.get("login.url", ""))
        self.portal_user.setText(props.get("login.user", ""))
        self.portal_pass.setText(props.get("login.pass", ""))
        self.default_state.setText(_get("state", "Default"))

    def _collect_config(self) -> dict:
        return {
            "firmware.csv": self.firmware_csv_value,
            "audit.csv": self.audit_csv_value,
            "firmware.json": self.firmware_json_value,
            "login.json": self.login_json_value,
            "login.url": self.portal_url.text().strip(),
            "login.user": self.portal_user.text().strip(),
            "login.pass": self.portal_pass.text().strip(),
            "state": self.default_state.text().strip(),
        }

    def _save_config(self) -> None:
        write_properties(self.config_path, self._collect_config())
        self._append_log(f"Saved config to {self.config_path}")

    def _start_backend(self) -> None:
        if self.backend_process and self.backend_process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, APP_TITLE, "Backend is already running.")
            return
        if self.build_process and self.build_process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, APP_TITLE, "Build is already running.")
            return

        self.stop_requested = False
        self._save_config()
        self._append_log("servers.json generation will be handled by the Java backend.")

        jar = find_jar(self.target_dir)
        if not jar:
            self._append_log("No JAR found in target/. Running Maven package...")
            self._run_maven_build()
            return

        self._run_java(jar)

    def _run_maven_build(self) -> None:
        if _is_frozen():
            self._append_log("Build is not available in standalone mode.")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            return
        if self.build_process and self.build_process.state() != QProcess.ProcessState.NotRunning:
            return
        mvn = shutil.which("mvn") or shutil.which("mvn.cmd")
        if not mvn:
            self._append_log("Maven not found on PATH. Please install Maven or add it to PATH.")
            QMessageBox.warning(
                self,
                APP_TITLE,
                "Maven not found on PATH. Please install Maven or add it to PATH.",
            )
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            return
        self.build_process = QProcess(self)
        self.build_process.setWorkingDirectory(str(self.repo_root))
        self.build_process.readyReadStandardOutput.connect(
            lambda: self._append_process_output(self.build_process)
        )
        self.build_process.readyReadStandardError.connect(
            lambda: self._append_process_output(self.build_process)
        )
        self.build_process.finished.connect(self._on_build_finished)
        self.build_process.errorOccurred.connect(
            lambda err: self._on_process_error("Build", err)
        )
        self._append_log("Running Maven build: mvn -q -DskipTests package")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.build_process.start(mvn, ["-q", "-DskipTests", "package"])

    def _on_build_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self.build_process = None
        if self.stop_requested:
            self._append_log("Build stopped.")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            return
        if exit_status != QProcess.ExitStatus.NormalExit or exit_code != 0:
            self._append_log(f"Build failed (exit code {exit_code}).")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            return
        jar = find_jar(self.target_dir)
        if not jar:
            self._append_log("Build finished but no JAR was found in target/.")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            return
        self._run_java(jar)

    def _run_java(self, jar: Path) -> None:
        self.backend_process = QProcess(self)
        if _is_frozen():
            self.backend_process.setWorkingDirectory(str(USER_DATA_DIR))
        else:
            self.backend_process.setWorkingDirectory(str(self.repo_root))
        self.backend_process.readyReadStandardOutput.connect(
            lambda: self._append_process_output(self.backend_process)
        )
        self.backend_process.readyReadStandardError.connect(
            lambda: self._append_process_output(self.backend_process)
        )
        self.backend_process.finished.connect(self._on_backend_finished)
        self.backend_process.errorOccurred.connect(
            lambda err: self._on_process_error("Backend", err)
        )
        self._append_log(f"Starting backend: {jar.name}")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        java_cmd = self._resolve_java_cmd()
        if not java_cmd:
            self._append_log("Java runtime not found. Please install Java 21+ or bundle a runtime.")
            QMessageBox.warning(
                self,
                APP_TITLE,
                "Java runtime not found. Please install Java 21+ or bundle a runtime.",
            )
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            return
        self.backend_process.start(
            java_cmd,
            [f"-Dfota.config={self.config_path}", "-jar", str(jar)],
        )

    def _resolve_java_cmd(self) -> str | None:
        # Prefer bundled runtime in standalone mode.
        if _is_frozen():
            runtime_java = _resource_path("runtime") / "bin" / "java.exe"
            if runtime_java.exists():
                return str(runtime_java)
        return shutil.which("java")

    def _resolve_path(self, value: str) -> Path:
        if not value:
            return self.repo_root
        path = Path(value)
        return path if path.is_absolute() else (self.repo_root / path)

    def _stop_backend(self) -> None:
        self.stop_requested = True
        if self.build_process and self.build_process.state() != QProcess.ProcessState.NotRunning:
            self._stop_process(self.build_process, "Build")
            self.build_process = None
        if self.backend_process and self.backend_process.state() != QProcess.ProcessState.NotRunning:
            self._stop_process(self.backend_process, "Backend")
            self.backend_process = None
            self._append_log("Backend stopped.")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_backend_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self.backend_process = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if self.stop_requested:
            return
        if exit_status == QProcess.ExitStatus.NormalExit:
            self._append_log(f"Backend exited (code {exit_code}).")
        else:
            self._append_log("Backend crashed.")

    def _append_process_output(self, proc: QProcess | None) -> None:
        if proc is None:
            return
        data = proc.readAllStandardOutput().data().decode(errors="ignore")
        err = proc.readAllStandardError().data().decode(errors="ignore")
        if data:
            self._append_log(data.rstrip())
        if err:
            self._append_log(err.rstrip())

    def _on_process_error(self, label: str, err: QProcess.ProcessError) -> None:
        self._append_log(f"{label} process error: {err.name}")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _append_log(self, text: str) -> None:
        if not text:
            return
        self.log.appendPlainText(text)

    def _stop_process(self, proc: QProcess, label: str) -> None:
        proc.terminate()
        proc.waitForFinished(5000)
        if proc.state() != QProcess.ProcessState.NotRunning:
            self._append_log(f"{label} did not stop on terminate; killing...")
            proc.kill()
            proc.waitForFinished(3000)
        if proc.state() != QProcess.ProcessState.NotRunning:
            pid = proc.processId()
            if pid:
                try:
                    if sys.platform.startswith("win"):
                        QProcess.execute("taskkill", ["/PID", str(pid), "/T", "/F"])
                    else:
                        QProcess.execute("kill", ["-9", str(pid)])
                    proc.waitForFinished(3000)
                except Exception as exc:
                    self._append_log(f"{label} force kill failed: {exc}")

    def closeEvent(self, event) -> None:
        self._stop_backend()
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
