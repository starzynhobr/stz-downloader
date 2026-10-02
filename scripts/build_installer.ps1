# Build the Inno Setup installer for STZ Downloader.
#
# Runs the PyInstaller onedir build first unless -SkipAppBuild is passed, then
# compiles packaging\inno\stz-downloader.iss. The version is read from
# pyproject.toml so the installer can never disagree with the app about which
# version it is.

param(
    [switch]$SkipAppBuild,
    # Package the Tauri desktop build (dist\stz-desktop) instead of the Qt one.
    [switch]$Desktop,
    [string]$OutDir = "$PSScriptRoot\..\dist"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
$iss = Join-Path $root "packaging\inno\stz-downloader.iss"
$appDir = Join-Path $OutDir $(if ($Desktop) { "stz-desktop" } else { "stz-downloader" })

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
$appVersion = $Matches[1]
$version = $appVersion
while (($version.Split(".")).Count -lt 4) { $version = "$version.0" }

if (-not $SkipAppBuild) {
    Write-Host "Building the frozen app..."
    $builder = if ($Desktop) { "build_desktop.ps1" } else { "build_windows.ps1" }
    & (Join-Path $PSScriptRoot $builder) -OutDir $OutDir
}

if (-not (Test-Path (Join-Path $appDir "stz-downloader.exe"))) {
    throw "Frozen app not found at '$appDir'. Run scripts\build_windows.ps1 first."
}

$iscc = Find-ISCC
Write-Host "Compiling installer with $iscc (version $version)"
$outputName = if ($Desktop) { "stz-downloader-$version-desktop-setup" } else { "stz-downloader-$version-setup" }
& $iscc "/DAppVersion=$version" "/DSourceDir=$((Resolve-Path $appDir).Path)" "/DOutputName=$outputName" $iss
if ($LASTEXITCODE -ne 0) {
    throw "ISCC failed with exit code $LASTEXITCODE"
}

# Checksums uploaded with the release; the in-app updater refuses to run an
# installer whose SHA-256 is not listed here (or in GitHub's asset digest).
$installer = Join-Path $OutDir "$outputName.exe"
$sumsFile = Join-Path $OutDir "SHA256SUMS.txt"
$sumsTargets = @(Get-Item $installer) + @(Get-ChildItem $OutDir -Filter "stz-extension-*-$appVersion.zip" -ErrorAction SilentlyContinue)
$lines = foreach ($f in $sumsTargets) { "{0}  {1}" -f (Get-FileHash -Algorithm SHA256 $f.FullName).Hash.ToLower(), $f.Name }
Set-Content -Path $sumsFile -Value $lines -Encoding ascii
Write-Host "`nInstaller: $installer"
Write-Host "Checksums: $sumsFile"
