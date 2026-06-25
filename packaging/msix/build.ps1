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
    [string]$AppDir    = "$PSScriptRoot\..\..\dist\stz-downloader"
)

$ErrorActionPreference = "Stop"
$pfx = "$OutDir\stz-downloader-dev.pfx"
$cer = "$OutDir\stz-downloader-dev.cer"
$layout = "$OutDir\msix-layout"
$msix = "$OutDir\stz-downloader.msix"
$pwd = ConvertTo-SecureString "stz-dev" -AsPlainText -Force

# 1. Self-signed cert (create once, reuse if present)
$cert = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -eq $Publisher } | Select-Object -First 1
if (-not $cert) {
    Write-Host "Creating self-signed certificate $Publisher"
    $cert = New-SelfSignedCertificate -Type Custom -Subject $Publisher `
        -KeyUsage DigitalSignature -FriendlyName "stz-downloader dev" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
    Export-PfxCertificate -Cert $cert -FilePath $pfx -Password $pwd | Out-Null
    Export-Certificate   -Cert $cert -FilePath $cer | Out-Null
    Write-Host "Exported $cer  (import into Trusted People to install)"
}

# 2. Stage layout
if (Test-Path $layout) { Remove-Item -Recurse -Force $layout }
New-Item -ItemType Directory -Force $layout | Out-Null
Copy-Item -Recurse "$AppDir\*" $layout
Copy-Item "$PSScriptRoot\AppxManifest.xml" "$layout\AppxManifest.xml"
Copy-Item -Recurse "$PSScriptRoot\Assets" "$layout\Assets" -ErrorAction SilentlyContinue

# 3. Pack
& makeappx.exe pack /d $layout /p $msix /o

# 4. Sign
& signtool.exe sign /fd SHA256 /a /f $pfx /p "stz-dev" $msix

Write-Host "`nBuilt and signed: $msix"
