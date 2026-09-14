# run-host-tests.ps1 -- build and run the host-side unit tests for the pure
# logic modules (can_codec, ringbuf).  These use clang from PATH or an explicit
# -Compiler argument; they never touch the ARM toolchain.
#
# Usage:  powershell -NoProfile -ExecutionPolicy Bypass -File tools/run-host-tests.ps1 [-Compiler clang]
param(
    [string]$Compiler = $env:CC
)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if ($Compiler) {
    $compilerCommand = Get-Command $Compiler -ErrorAction SilentlyContinue
} else {
    $compilerCommand = Get-Command clang -ErrorAction SilentlyContinue
}
if (-not $compilerCommand) {
    Write-Host "clang not found; put it on PATH, set CC, or pass -Compiler <path>" -ForegroundColor Red
    exit 2
}
$CC = $compilerCommand.Source

$out = 'build/tests'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$failed = 0

$tests = @(
    @{ name = 'can_bitrate'; src = @('tools/tests/can_bitrate_test.c','Core/Src/can_bitrate.c') }
    @{ name = 'can_codec'; src = @('tools/tests/can_codec_test.c','Core/Src/can_codec.c') }
    @{ name = 'ringbuf';   src = @('tools/tests/ringbuf_test.c') }
)

foreach ($t in $tests) {
    Write-Host "=== $($t.name) ===" -ForegroundColor Cyan
    $exe = "$out/$($t.name)_test.exe"
    & $CC -Wall -Wextra -O1 -ICore/Inc -o $exe @($t.src) 2>&1 | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) { Write-Host "build failed: $($t.name)" -ForegroundColor Red; $failed++; continue }
    & $exe
    if ($LASTEXITCODE -ne 0) { $failed++ }
    Write-Host ""
}

if ($failed) { Write-Host "$failed test binary/binaries FAILED" -ForegroundColor Red; exit 1 }
Write-Host "all host tests passed" -ForegroundColor Green
