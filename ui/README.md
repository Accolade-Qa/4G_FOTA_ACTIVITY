# FOTA PyQt6 UI

This UI edits `config.properties`, builds the Java backend if needed, and runs it.

## Run (development)

```powershell
python -m pip install -r ui/requirements.txt
python ui/pyqt6_app.py
```

## Build EXE (PyInstaller)

```powershell
python -m pip install pyinstaller
pyinstaller --noconsole --onefile --name FOTA_UI ui/pyqt6_app.py
```

Notes:
- The EXE still needs Java to run the backend JAR.
- If no JAR exists in `target`, the UI will call `mvn -DskipTests package`.
- To avoid Maven at runtime, build once (`mvn -DskipTests package`) and ship the `target` folder with the EXE.
