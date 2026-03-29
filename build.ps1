param(
    [switch]$SkipPythonDeps
)

$ErrorActionPreference = 'Stop'

Write-Host 'Cleaning up running UI/backend processes...'
Get-Process FOTA_UI -ErrorAction SilentlyContinue | Stop-Process -Force
Get-CimInstance Win32_Process |
    Where-Object { $_.Name -in @('java.exe','javaw.exe') -and $_.CommandLine -like '*FOTA_ACTIVITY-Version-1.0.2.jar*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }


function Remove-PathWithRetry {
    param(
        [string]$Path,
        [int]$Retries = 5,
        [int]$DelayMs = 500
    )
    if (-not (Test-Path $Path)) { return }
    for ($i = 1; $i -le $Retries; $i++) {
        try {
            Remove-Item -Recurse -Force -LiteralPath $Path -ErrorAction Stop
            return
        } catch {
            Start-Sleep -Milliseconds $DelayMs
        }
    }
    $stamp = (Get-Date).ToString('yyyyMMdd_HHmmss')
    $fallback = "${Path}_locked_$stamp"
    try {
        Rename-Item -LiteralPath $Path -NewName $fallback -ErrorAction Stop
    } catch {
        Write-Host "Could not remove or rename $Path. Please close any running EXE and try again."
    }
}

Write-Host 'Cleaning previous dist folder...'
Remove-PathWithRetry -Path 'dist\\FOTA_UI'

Write-Host 'Building Java backend (fat JAR)...'
mvn -DskipTests package

Write-Host 'Copying backend JAR into UI bundle...'
New-Item -ItemType Directory -Force -Path ui\\backend | Out-Null
Copy-Item -Force target\\FOTA_ACTIVITY-Version-1.0.2-shaded.jar ui\\backend\\FOTA_ACTIVITY-Version-1.0.2.jar

Write-Host 'Preparing UI defaults from input files...'
New-Item -ItemType Directory -Force -Path ui\\defaults | Out-Null
if (Test-Path input\\fota_batch.csv) { Copy-Item -Force input\\fota_batch.csv ui\\defaults\\ }
if (Test-Path input\\Server_Inputs.xlsx) { Copy-Item -Force input\\Server_Inputs.xlsx ui\\defaults\\ }
if (Test-Path input\\servers.json) { Copy-Item -Force input\\servers.json ui\\defaults\\ }

if (-not $SkipPythonDeps) {
    Write-Host 'Installing Python UI dependencies...'
    pip install -r ui\requirements.txt
}

Write-Host 'Preparing EXE icon...'
if (Test-Path ui\\assets\\logo.png) {
    python ui\\tools\\make_icon.py ui\\assets\\logo.png ui\\assets\\logo.ico
} else {
    Write-Host 'logo.png not found; skipping icon generation.'
}

Write-Host 'Building UI bundle with PyInstaller...'
pyinstaller -y --distpath ui\\dist --workpath ui\\build FOTA_UI.spec

Write-Host 'Publishing bundle to dist\\FOTA_UI...'
$uiDist = 'ui\\dist\\FOTA_UI'
$rootDist = 'dist\\FOTA_UI'
if (Test-Path $uiDist) {
    New-Item -ItemType Directory -Force -Path dist | Out-Null
    Copy-Item -Recurse -Force $uiDist dist\\
} elseif (Test-Path $rootDist) {
    Write-Host 'PyInstaller output already in dist\\FOTA_UI.'
} else {
    throw 'PyInstaller output not found in ui\\dist\\FOTA_UI or dist\\FOTA_UI.'
}

Write-Host 'Build complete.'
Write-Host 'Output: dist\\FOTA_UI\\FOTA_UI.exe'
