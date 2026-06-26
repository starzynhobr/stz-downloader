# Build a self-signed MSIX package for stz-downloader.
#
# Prerequisites:
#   - Windows SDK (makeappx.exe, signtool.exe on PATH or in the SDK bin folder)
#   - A frozen build of the app in dist/stz-downloader/ (see PyInstaller below)
#
# Steps performed:
#   1. Create a self-signed code-signing cert (once) matching the manifest Publisher.
#   2. Stage files + manifest into a layout folder.
#   3. makeappx pack  -> stz-downloader.msix
#   4. signtool sign  -> signed package
#
# To INSTALL on another machine you must first trust the certificate:
#   Import stz-downloader-dev.cer into "Local Machine > Trusted People"
#   (or Trusted Root). Then double-click the .msix.

param(
    [string]$Publisher = "CN=stz-downloader (dev)",
    [string]$OutDir    = "$PSScriptRoot\..\..\dist",
    [string]$AppDir    = "$PSScriptRoot\..\..\dist\stz-downloader",
    [string]$AssetsDir = "$PSScriptRoot\..\..\assets"
)

$ErrorActionPreference = "Stop"
$pfx = "$OutDir\stz-downloader-dev.pfx"
$cer = "$OutDir\stz-downloader-dev.cer"
$layout = "$OutDir\msix-layout"
$msix = "$OutDir\stz-downloader.msix"
$installer = "$OutDir\install.ps1"
$installerBat = "$OutDir\install.bat"
$pwd = ConvertTo-SecureString "stz-dev" -AsPlainText -Force
$requiredAssets = @(
    "StoreLogo.png",
    "Square150x150Logo.png",
    "Square44x44Logo.png",
    "Square310x310Logo.png",
    "Square71x71Logo.png",
    "stz-downloader.ico"
)

function Find-SdkTool([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $kits = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
    if (Test-Path $kits) {
        $candidate = Get-ChildItem $kits -Recurse -Filter $Name -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match "\\x64\\" } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($candidate) {
            return $candidate.FullName
        }
    }

    throw "$Name was not found. Install the Windows SDK or add its x64 bin folder to PATH."
}

New-Item -ItemType Directory -Force $OutDir | Out-Null

if (-not (Test-Path $AppDir)) {
    throw "Frozen app not found at '$AppDir'. Run scripts\build_windows.ps1 from the repository root before building the MSIX package."
}

foreach ($asset in $requiredAssets) {
    $path = Join-Path $AssetsDir $asset
    if (-not (Test-Path $path)) {
        throw "Missing MSIX asset '$asset' in '$AssetsDir'. Add your logo assets before building the MSIX package."
    }
}

$makeappx = Find-SdkTool "makeappx.exe"
$signtool = Find-SdkTool "signtool.exe"

# 1. Self-signed cert (create once, reuse if present)
$cert = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -eq $Publisher } | Select-Object -First 1
if (-not $cert) {
    Write-Host "Creating self-signed certificate $Publisher"
    $cert = New-SelfSignedCertificate -Type Custom -Subject $Publisher `
        -KeyUsage DigitalSignature -FriendlyName "stz-downloader dev" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
}
if (-not (Test-Path $pfx)) {
    Export-PfxCertificate -Cert $cert -FilePath $pfx -Password $pwd | Out-Null
}
if (-not (Test-Path $cer)) {
    Export-Certificate   -Cert $cert -FilePath $cer | Out-Null
    Write-Host "Exported $cer  (import into Trusted People to install)"
}

# 2. Stage layout
if (Test-Path $layout) { Remove-Item -Recurse -Force $layout }
New-Item -ItemType Directory -Force $layout | Out-Null
Copy-Item -Recurse "$AppDir\*" $layout
Copy-Item "$PSScriptRoot\AppxManifest.xml" "$layout\AppxManifest.xml"
Copy-Item -Recurse $AssetsDir "$layout\Assets"

# 3. Pack
& $makeappx pack /d $layout /p $msix /o
if ($LASTEXITCODE -ne 0) {
    throw "makeappx failed with exit code $LASTEXITCODE"
}

# 4. Sign
& $signtool sign /fd SHA256 /a /f $pfx /p "stz-dev" $msix
if ($LASTEXITCODE -ne 0) {
    throw "signtool failed with exit code $LASTEXITCODE"
}

Copy-Item "$PSScriptRoot\install.ps1" $installer
Copy-Item "$PSScriptRoot\install.bat" $installerBat

Write-Host "`nBuilt and signed: $msix"
Write-Host "Installer script: $installer"
Write-Host "Double-click installer: $installerBat"
