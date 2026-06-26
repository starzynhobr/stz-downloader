# Build the Windows onedir app used by packaging/msix/build.ps1.

param(
    [string]$OutDir = "$PSScriptRoot\..\dist"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
$dist = (New-Item -ItemType Directory -Force $OutDir).FullName
$work = Join-Path $dist "pyinstaller-work"
$spec = Join-Path $dist "pyinstaller-spec"
$src = Join-Path $root "src"
$qml = Join-Path $root "src\stz_downloader\ui\qml"
$i18n = Join-Path $root "src\stz_downloader\ui\i18n"
$aria2Exe = Join-Path $root "third_party\aria2\aria2c.exe"
$aria2License = Join-Path $root "third_party\aria2\LICENSE"
$aria2Source = Join-Path $root "third_party\aria2\SOURCE.md"
$entry = Join-Path $root "scripts\pyinstaller_entry.py"
$icon = Join-Path $root "assets\stz-downloader.ico"

if (-not (Get-Command pyinstaller.exe -ErrorAction SilentlyContinue)) {
    throw "pyinstaller.exe was not found on PATH. Activate .venv and run: uv pip install pyinstaller"
}

Push-Location $root
try {
    pyinstaller `
        --noconfirm `
        --clean `
        --onedir `
        --windowed `
        --name stz-downloader `
        --paths $src `
        --icon $icon `
        --distpath $dist `
        --workpath $work `
        --specpath $spec `
        --add-data "${qml};stz_downloader\ui\qml" `
        --add-data "${i18n};stz_downloader\ui\i18n" `
        --add-binary "${aria2Exe};third_party\aria2" `
        --add-data "${aria2License};third_party\aria2" `
        --add-data "${aria2Source};third_party\aria2" `
        --hidden-import PySide6.QtWebSockets `
        --collect-submodules uvicorn `
        --collect-submodules websockets `
        --collect-submodules httptools `
        --collect-submodules watchfiles `
        --collect-submodules anyio `
        $entry
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

Write-Host "`nBuilt frozen app: $dist\stz-downloader"
Write-Host "Next: packaging\msix\build.ps1"
