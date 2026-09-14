param(
    [ValidatePattern('^v[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$')]
    [string]$Version = 'v0.1.0-beta',
    [string]$FirmwareDirectory = '',
    [string]$HostExecutable = ''
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot

if (-not $FirmwareDirectory) {
    $candidates = @(
        (Join-Path $ProjectRoot 'build\gcc-Release'),
        (Join-Path $ProjectRoot 'build\verify\Release'),
        (Join-Path $ProjectRoot 'build\Release')
    )
    $FirmwareDirectory = $candidates |
        Where-Object {
            (Test-Path (Join-Path $_ 'c6t6.hex')) -and
            (Test-Path (Join-Path $_ 'c6t6.bin'))
        } |
        Select-Object -First 1
}

if (-not $HostExecutable) {
    $HostExecutable = Join-Path $ProjectRoot 'host_app\dist\UART-CAN-Host.exe'
}

if (-not $FirmwareDirectory) {
    throw 'No c6t6.hex/c6t6.bin pair found. Build the Release firmware first or pass -FirmwareDirectory.'
}
if (-not (Test-Path -LiteralPath $HostExecutable -PathType Leaf)) {
    throw "Host executable not found: $HostExecutable. Run host_app/build_exe.ps1 first."
}

$hexSource = Join-Path $FirmwareDirectory 'c6t6.hex'
$binSource = Join-Path $FirmwareDirectory 'c6t6.bin'
$outputDirectory = Join-Path $ProjectRoot "release\$Version"
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

$versionLabel = $Version.TrimStart('v')
$assets = @(
    @{ Source = $HostExecutable; Name = "UART-CAN-Host-$versionLabel-windows-x64.exe" },
    @{ Source = $hexSource; Name = "c6t6-$versionLabel.hex" },
    @{ Source = $binSource; Name = "c6t6-$versionLabel.bin" },
    @{ Source = (Join-Path $ProjectRoot 'LICENSE'); Name = 'LICENSE.txt' },
    @{ Source = (Join-Path $ProjectRoot 'THIRD_PARTY_NOTICES.md'); Name = 'THIRD_PARTY_NOTICES.md' },
    @{ Source = (Join-Path $ProjectRoot 'Drivers\STM32F1xx_HAL_Driver\LICENSE.txt'); Name = 'STM32F1xx-HAL-LICENSE.txt' },
    @{ Source = (Join-Path $ProjectRoot 'Drivers\CMSIS\LICENSE.txt'); Name = 'CMSIS-LICENSE.txt' },
    @{ Source = (Join-Path $ProjectRoot 'Drivers\CMSIS\Device\ST\STM32F1xx\LICENSE.txt'); Name = 'STM32F1xx-CMSIS-LICENSE.txt' },
    @{ Source = (Join-Path $ProjectRoot 'licenses\LGPL-3.0.txt'); Name = 'LGPL-3.0.txt' },
    @{ Source = (Join-Path $ProjectRoot 'licenses\GPL-3.0.txt'); Name = 'GPL-3.0.txt' },
    @{ Source = (Join-Path $ProjectRoot 'licenses\PYTHON-LICENSE.txt'); Name = 'PYTHON-LICENSE.txt' },
    @{ Source = (Join-Path $ProjectRoot 'licenses\PYSERIAL-LICENSE.txt'); Name = 'PYSERIAL-LICENSE.txt' },
    @{ Source = (Join-Path $ProjectRoot 'licenses\PYINSTALLER-LICENSE.txt'); Name = 'PYINSTALLER-LICENSE.txt' }
)

foreach ($asset in $assets) {
    Copy-Item -LiteralPath $asset.Source -Destination (Join-Path $outputDirectory $asset.Name) -Force
}

$checksumPath = Join-Path $outputDirectory 'SHA256SUMS.txt'
$checksumLines = foreach ($asset in $assets) {
    $assetPath = Join-Path $outputDirectory $asset.Name
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $assetPath).Hash.ToLowerInvariant()
    "$hash  $($asset.Name)"
}
[System.IO.File]::WriteAllLines(
    $checksumPath,
    [string[]]$checksumLines,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "Release assets: $outputDirectory"
Get-ChildItem -LiteralPath $outputDirectory -File |
    Select-Object Name, Length, @{Name='SHA256'; Expression={(Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash}}
