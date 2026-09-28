# Build the Inno Setup installer for STZ Downloader.
#
# Runs the PyInstaller onedir build first unless -SkipAppBuild is passed, then
# compiles packaging\inno\stz-downloader.iss. The version is read from
# pyproject.toml so the installer can never disagree with the app about which
# version it is.

param(
    [switch]$SkipAppBuild,
    [string]$OutDir = "$PSScriptRoot\..\dist"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
$iss = Join-Path $root "packaging\inno\stz-downloader.iss"
$appDir = Join-Path $OutDir "stz-downloader"

function Find-ISCC {
    $cmd = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($base in @(${env:ProgramFiles(x86)}, $env:ProgramFiles)) {
        if (-not $base) { continue }
        foreach ($version in @("Inno Setup 6", "Inno Setup 5")) {
            $candidate = Join-Path $base "$version\ISCC.exe"
            if (Test-Path $candidate) { return $candidate }
        }
    }
    throw "ISCC.exe was not found. Install Inno Setup or add its folder to PATH."
}

# Version from pyproject.toml -- Inno wants four numeric parts.
$pyproject = Get-Content (Join-Path $root "pyproject.toml") -Raw
if ($pyproject -notmatch '(?m)^version\s*=\s*"([^"]+)"') {
    throw "Could not read version from pyproject.toml"
}
$version = $Matches[1]
while (($version.Split(".")).Count -lt 4) { $version = "$version.0" }

if (-not $SkipAppBuild) {
    Write-Host "Building the frozen app..."
    & (Join-Path $PSScriptRoot "build_windows.ps1") -OutDir $OutDir
}

if (-not (Test-Path (Join-Path $appDir "stz-downloader.exe"))) {
    throw "Frozen app not found at '$appDir'. Run scripts\build_windows.ps1 first."
}

$iscc = Find-ISCC
Write-Host "Compiling installer with $iscc (version $version)"
& $iscc "/DAppVersion=$version" $iss
if ($LASTEXITCODE -ne 0) {
    throw "ISCC failed with exit code $LASTEXITCODE"
}

Write-Host "`nInstaller: $OutDir\stz-downloader-$version-setup.exe"
