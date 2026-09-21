# verify-build.ps1 -- standalone rebuild used to validate changes in this
# sandbox, where `ninja` cannot run.  Mirrors cmake/starm-clang.cmake exactly.
#
# Usage:  pwsh -File tools/verify-build.ps1 [-Config Debug|Release] [-Bin]
#         [-Compiler <clang>] [-GnuToolchainRoot <root>]
param(
    [ValidateSet('Debug','Release')] [string]$Config = 'Release',
    [switch]$Bin,
    [string]$Compiler = $env:STARM_CLANG,
    [string]$GnuToolchainRoot = $env:GNU_TOOLCHAIN_ROOT
)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$toolSuffix = if ([System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT) { '.exe' } else { '' }

if (-not $Compiler -and $env:STARM_TOOLCHAIN_PATH) {
    $Compiler = Join-Path $env:STARM_TOOLCHAIN_PATH "clang$toolSuffix"
}
if ($Compiler) {
    $compilerCommand = Get-Command $Compiler -ErrorAction SilentlyContinue
} else {
    $compilerCommand = Get-Command clang -ErrorAction SilentlyContinue
}
if (-not $compilerCommand) {
    throw 'clang not found; set STARM_CLANG/STARM_TOOLCHAIN_PATH or pass -Compiler <path>'
}
$CC = $compilerCommand.Source

if ($GnuToolchainRoot) {
    $gnuBin = Join-Path $GnuToolchainRoot 'bin'
    $gccCommand = Get-Command (Join-Path $gnuBin "arm-none-eabi-gcc$toolSuffix") -ErrorAction SilentlyContinue
} else {
    $gccCommand = Get-Command arm-none-eabi-gcc -ErrorAction SilentlyContinue
    if ($gccCommand) {
        $gnuBin = Split-Path -Parent $gccCommand.Source
        $GnuToolchainRoot = Split-Path -Parent $gnuBin
    }
}
if (-not $gccCommand) {
    throw 'GNU Arm toolchain not found; set GNU_TOOLCHAIN_ROOT or pass -GnuToolchainRoot <root>'
}

$GNU = $GnuToolchainRoot -replace '\\', '/'
$gnuLibc = (& $gccCommand.Source -mcpu=cortex-m3 -mthumb '-print-file-name=libc.a').Trim()
$gnuLibgcc = (& $gccCommand.Source -mcpu=cortex-m3 -mthumb '-print-file-name=libgcc.a').Trim()
if (-not (Test-Path -LiteralPath $gnuLibc) -or -not (Test-Path -LiteralPath $gnuLibgcc)) {
    throw 'GNU Cortex-M3 Thumb runtime libraries not found'
}
$runtimeSearch = @("-L$(Split-Path -Parent $gnuLibc)", "-L$(Split-Path -Parent $gnuLibgcc)")
$SIZE = Join-Path $gnuBin "arm-none-eabi-size$toolSuffix"
$OBJCOPY = Join-Path $gnuBin "arm-none-eabi-objcopy$toolSuffix"
$READELF = Join-Path $gnuBin "arm-none-eabi-readelf$toolSuffix"
if (-not (Test-Path $SIZE)) { $SIZE = (Get-Command arm-none-eabi-size -ErrorAction Stop).Source }
if (-not (Test-Path $OBJCOPY)) { $OBJCOPY = (Get-Command arm-none-eabi-objcopy -ErrorAction Stop).Source }
if (-not (Test-Path $READELF)) { $READELF = (Get-Command arm-none-eabi-readelf -ErrorAction Stop).Source }

$out = "build/verify/$Config"
New-Item -ItemType Directory -Force -Path $out | Out-Null

$inc = @(
    "-I$root/Core/Inc"
    "-I$root/Drivers/STM32F1xx_HAL_Driver/Inc"
    "-I$root/Drivers/STM32F1xx_HAL_Driver/Inc/Legacy"
    "-I$root/Drivers/CMSIS/Device/ST/STM32F1xx/Include"
    "-I$root/Drivers/CMSIS/Include"
)

$src = @(
    'Core/Src/main.c'
    'Core/Src/can_bitrate.c'
    'Core/Src/can_codec.c'
    'Core/Src/stm32f1xx_it.c'
    'Core/Src/stm32f1xx_hal_msp.c'
    'Core/Src/sysmem.c'
    'Core/Src/syscalls.c'
    'Core/Src/system_stm32f1xx.c'
    'Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_gpio_ex.c'
    'Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_can.c'
    'Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal.c'
    'Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_rcc.c'
    'Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_rcc_ex.c'
    'Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_gpio.c'
    'Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_dma.c'
    'Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_cortex.c'
    'Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_pwr.c'
    'Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_flash.c'
    'Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_flash_ex.c'
    'Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_exti.c'
    'Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_uart.c'
)

if ($Config -eq 'Debug') { $opt = @('-O0','-g3','-DDEBUG') } else { $opt = @('-Os','-g0','-DNDEBUG') }

$defs = @('-DSTM32F103x6','-DUSE_HAL_DRIVER')
$common = @('--target=arm-none-eabi','-mcpu=cortex-m3','-mthumb','-Wall','-Wextra',
            '-fdata-sections','-ffunction-sections','-std=gnu11','-Wno-unused-parameter')

$objs = @()
$warnings = 0
foreach ($s in $src) {
    $o = "$out/" + ($s -replace '[\\/]','_') + '.o'
    $lines = & $CC @defs @inc @common @opt -o $o -c $s 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $s" -ForegroundColor Red
        $lines | ForEach-Object { Write-Host $_ }
        exit 1
    }
    foreach ($l in $lines) { if ($l -match 'warning:') { $warnings++; Write-Host $l -ForegroundColor Yellow } }
    $objs += $o
}

$asmOut = "$out/startup.o"
$lines = & $CC @defs @inc @common @opt -x assembler-with-cpp -o $asmOut -c startup_stm32f103x6.s 2>&1
if ($LASTEXITCODE -ne 0) { $lines | ForEach-Object { Write-Host $_ }; exit 1 }
$objs += $asmOut

$elf = "$out/c6t6.elf"
& $CC --target=arm-none-eabi -mcpu=cortex-m3 -mthumb "-rtlib=libgcc" "--gcc-toolchain=$GNU" `
      -nostdlib @runtimeSearch -lc_nano -lm -lgcc `
      "-T$root/STM32F103XX_FLASH.ld" "-Wl,-Map=$out/c6t6.map" `
      '-Wl,--gc-sections' -z noexecstack '-Wl,--print-memory-usage' `
      -o $elf @objs 2>&1 | Where-Object { $_ -notmatch 'multilib|unused during compilation' }
if ($LASTEXITCODE -ne 0) { Write-Host "LINK FAILED" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "compiler warnings: $warnings" -ForegroundColor $(if ($warnings) { 'Yellow' } else { 'Green' })
& $SIZE $elf
Write-Host ""
Write-Host "LOAD segments (must all be at low file offsets):"
& $READELF -l $elf 2>&1 | Select-String 'LOAD'

if ($Bin) {
    & $OBJCOPY -O binary $elf "$out/c6t6.bin"
    & $OBJCOPY -O ihex   $elf "$out/c6t6.hex"
    $b = Get-Item "$out/c6t6.bin"
    Write-Host ""
    Write-Host ("bin = {0} bytes, hex = {1} bytes" -f $b.Length, (Get-Item "$out/c6t6.hex").Length)
}
