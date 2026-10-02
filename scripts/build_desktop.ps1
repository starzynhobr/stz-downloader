# Build the Tauri desktop app into dist\stz-desktop.
#
# Layout (one folder, what the installer copies to {app}):
#   stz-downloader.exe               Tauri shell (UI, tray, clipboard)
#   stz-engine.exe                   headless bridge + aria2 manager, no Qt
#   stz-downloader-native-host.exe   browser Native Messaging helper
#   _internal\                       Python runtime shared by both helpers
#
# Needs the repo's .venv (with pyinstaller), Node and Rust.

param(
    [string]$OutDir = "$PSScriptRoot\..\dist"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
$dist = (New-Item -ItemType Directory -Force $OutDir).FullName
$work = Join-Path $dist "pyinstaller-work"
$spec = Join-Path $dist "pyinstaller-spec"
$engineDist = Join-Path $dist "engine-dist"
$nativeDist = Join-Path $dist "native-host-dist"
$appDir = Join-Path $dist "stz-desktop"
$src = Join-Path $root "src"
$icon = Join-Path $root "assets\stz-downloader.ico"
$aria2Dir = Join-Path $root "third_party\aria2"
$venvScripts = Join-Path $root ".venv\Scripts"

if (Test-Path $venvScripts) { $env:PATH = "$venvScripts;$env:PATH" }
if (-not (Get-Command pyinstaller.exe -ErrorAction SilentlyContinue)) {
    throw "pyinstaller.exe was not found. Set up .venv and run: uv pip install pyinstaller"
}

Push-Location $root
try {
    # Windowless: the shell starts it in the background.
    pyinstaller `
        --noconfirm `
        --clean `
        --onedir `
        --windowed `
        --name stz-engine `
        --paths $src `
        --icon $icon `
        --distpath $engineDist `
        --workpath $work `
        --specpath $spec `
        --add-binary "$aria2Dir\aria2c.exe;third_party\aria2" `
        --add-data "$aria2Dir\LICENSE;third_party\aria2" `
        --add-data "$aria2Dir\SOURCE.md;third_party\aria2" `
        --exclude-module PySide6 `
        --exclude-module shiboken6 `
        --collect-submodules uvicorn `
        --collect-submodules websockets `
        --collect-submodules httptools `
        --collect-submodules anyio `
        (Join-Path $root "scripts\engine_entry.py")
    if ($LASTEXITCODE -ne 0) { throw "Engine build failed with exit code $LASTEXITCODE" }

    # Console mode is required: Native Messaging talks over stdin/stdout.
    pyinstaller `
        --noconfirm `
        --clean `
        --onedir `
        --console `
        --name stz-downloader-native-host `
        --paths $src `
        --distpath $nativeDist `
        --workpath $work `
        --specpath $spec `
        --exclude-module PySide6 `
        --exclude-module shiboken6 `
        (Join-Path $root "scripts\native_host_entry.py")
    if ($LASTEXITCODE -ne 0) { throw "Native host build failed with exit code $LASTEXITCODE" }

    Push-Location (Join-Path $root "desktop")
    try {
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
        npx tauri build --no-bundle
        if ($LASTEXITCODE -ne 0) { throw "Tauri build failed with exit code $LASTEXITCODE" }
    }
    finally {
        Pop-Location
    }

    if (Test-Path $appDir) { Remove-Item -Recurse -Force $appDir }
    Copy-Item -Recurse (Join-Path $engineDist "stz-engine") $appDir
    # The native host shares the engine's _internal tree; only its launcher is copied.
    Copy-Item -Force (Join-Path $nativeDist "stz-downloader-native-host\stz-downloader-native-host.exe") $appDir
    Copy-Item -Force (Join-Path $root "desktop\src-tauri\target\release\stz-downloader.exe") $appDir
}
finally {
    Pop-Location
}

Write-Host "`nBuilt desktop app: $appDir"
