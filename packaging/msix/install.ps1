# Install the locally signed stz-downloader MSIX package.
#
# Keep this script next to:
#   - stz-downloader.msix
#   - stz-downloader-dev.cer

param(
    [string]$PackagePath = "$PSScriptRoot\stz-downloader.msix",
    [string]$CertificatePath = "$PSScriptRoot\stz-downloader-dev.cer"
)

$ErrorActionPreference = "Stop"

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Path $PackagePath)) {
    throw "MSIX package not found: $PackagePath"
}
if (-not (Test-Path $CertificatePath)) {
    throw "Certificate not found: $CertificatePath"
}

if (-not (Test-Admin)) {
    Write-Host "Administrator permission is required to trust the MSIX signing certificate."
    $args = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSCommandPath`"",
        "-PackagePath", "`"$PackagePath`"",
        "-CertificatePath", "`"$CertificatePath`""
    )
    Start-Process powershell.exe -Verb RunAs -ArgumentList $args
    exit
}

$peopleStore = "Cert:\LocalMachine\TrustedPeople"
$rootStore = "Cert:\LocalMachine\Root"

Write-Host "Importing certificate into $peopleStore"
Import-Certificate -FilePath $CertificatePath -CertStoreLocation $peopleStore | Out-Null

Write-Host "Importing certificate into $rootStore"
Import-Certificate -FilePath $CertificatePath -CertStoreLocation $rootStore | Out-Null

Write-Host "Closing running STZ Downloader processes"
Get-Process -Name "stz-downloader" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq "aria2c.exe" -and
        $_.ExecutablePath -like "*\stz-downloader_*"
    } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Write-Host "Installing package $PackagePath"
Add-AppxPackage -Path $PackagePath -ForceUpdateFromAnyVersion

Write-Host "Starting STZ Downloader"
$package = Get-AppxPackage -Name "stz-downloader" | Sort-Object Version -Descending | Select-Object -First 1
if ($package) {
    Start-Process explorer.exe "shell:AppsFolder\$($package.PackageFamilyName)!App"
}

Write-Host "`nSTZ Downloader installed."
