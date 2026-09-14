param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$HostAppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VirtualEnv = Join-Path $HostAppRoot ".venv"
$VirtualPython = Join-Path $VirtualEnv "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VirtualPython)) {
    & $Python -m venv $VirtualEnv
}

& $VirtualPython -m pip install --upgrade pip
& $VirtualPython -m pip install -r (Join-Path $HostAppRoot "requirements-release.txt")

Push-Location $HostAppRoot
try {
    & $VirtualPython -m PyInstaller `
        --noconfirm `
        --clean `
        (Join-Path $HostAppRoot "UART-CAN-Host.spec")
}
finally {
    Pop-Location
}

Write-Host "EXE: $(Join-Path $HostAppRoot 'dist\UART-CAN-Host.exe')"
