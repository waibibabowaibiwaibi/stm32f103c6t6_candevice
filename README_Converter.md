# STM32 native USB-CAN converter — firmware development notes

This is the detailed firmware/build reference. New users should start with the
[main README](README.md), the [five-minute quick start](docs/QUICK_START.md),
and the standalone [protocol reference](docs/PROTOCOL.md).

## Hardware
- **MCU**: STM32F103C6T6 (32 KB flash, 10 KB RAM)
- **CAN**: PB8 (RX), PB9 (TX), 500 kbit/s after reset; runtime-selectable from 10 kbit/s to 1 Mbit/s
- **USB device**: PA11 (D-), PA12 (D+), CDC ACM virtual serial port
- **Activity/status LED**: PC13, active-low; a 35 ms non-blocking pulse on accepted TX or received CAN frames, solid low in `Error_Handler`

Clock tree: HSE 8 MHz -> PLL x9 -> 72 MHz SYSCLK, APB1 36 MHz. USB uses
the PLL clock divided by 1.5 to obtain 48 MHz. CAN1 uses AFIO remap 2 so that
PA11/PA12 remain available to USB.
The USB device stack, CDC class glue, endpoint PMA layout, descriptors and PCD
low-level driver are generated from `c6t6.ioc` by STM32CubeMX. Project-specific
receive forwarding and transmit-state handling stay inside CubeMX `USER CODE`
blocks in `USB_DEVICE/App/usbd_cdc_if.c`.
Default CAN bit timing: `36 MHz / Prescaler(4) / (1 + TS1(15) + TS2(2)) = 500 kbit/s`,
sample point 88.9%. `Core/Src/can_bitrate.c` contains the exact timing table for
all nine supported rates; its host-side test verifies every divisor against the
36 MHz peripheral clock.

## Protocol

The device uses a text-based protocol similar to SLCAN.

### Sending CAN Messages (USB CDC -> CAN)

- **Standard Frame**: `tIIILDD...`
  - `t`: Identifier for Standard Frame
  - `III`: 3-digit Hex ID (e.g., `123`)
  - `L`: 1-digit Data Length Code (0-8)
  - `DD...`: Data bytes in Hex (2 digits per byte)
  - Example: `t12381122334455667788` (ID: 0x123, DLC: 8, Data: 0x11, 0x22, ...)

- **Extended Frame**: `TIIIIIIIILDD...`
  - `T`: Identifier for Extended Frame
  - `IIIIIIII`: 8-digit Hex ID
  - `L`: 1-digit Data Length Code (0-8)
  - `DD...`: Data bytes in Hex
  - Example: `T0000012381122334455667788`

- **Remote Frames**: use `r` / `R` in place of `t` / `T`, with no data bytes.
  Example: `r1238` (standard remote frame, ID 0x123, DLC 8).

- **Status Request**: send `V`. The device replies with one space-separated
  line of counters:

  ```
  V <can_rx> <can_tx> <uart_drop> <cmd_drop> <cmd_bad> <can_tx_drop> <uart_err> <can_recover>
  ```

  | field | meaning |
  |---|---|
  | `can_rx` | frames forwarded CAN -> USB CDC |
  | `can_tx` | frames accepted USB CDC -> CAN |
  | `uart_drop` | bytes/frames dropped because the USB TX ring was full; legacy field name retained for host compatibility |
  | `cmd_drop` | command lines dropped or too long |
  | `cmd_bad` | command lines that were frames but malformed |
  | `can_tx_drop` | frames dropped because all 3 CAN mailboxes were busy |
  | `uart_err` | reserved transport-error counter; legacy field name retained for host compatibility |
  | `can_recover` | successful CAN bus-off recoveries |

- **CAN bit rate**: send `S?` to query the active rate, or `S0` through `S8`
  to select 10, 20, 50, 100, 125, 250, 500, 800 or 1000 kbit/s. A successful
  query/change returns `S <bitrate>`; a failed change returns `E S`. Changing
  the rate stops bxCAN, calls `HAL_CAN_Init()` with the new timing, restores the
  filter and notifications, and restarts the controller. A failed change rolls
  back the previous `CAN_InitTypeDef`. The selection is not stored in Flash.

Terminate commands with `\r` (Carriage Return). `\n` is also accepted.

Every frame is length-checked against its identifier type before any data is
read, and a DLC outside 0..8 is rejected outright. Malformed frames are counted
in `cmd_bad` and otherwise ignored. Malformed `S` commands return `E S` and
increment `cmd_bad`; other input that is neither a frame nor a device command
is ignored silently.

### Receiving CAN Messages (CAN -> USB CDC)

The device outputs received CAN messages in the same format as above,
terminated with `\r`.

## Building

### CMake

Two toolchains are supported. The shared presets are available on Linux and in
CI; Windows keeps machine-specific paths in the ignored `CMakeUserPresets.json`
so they are never committed:

```sh
cmake --preset Release        # ATfE clang (-Os), GNU ld, newlib-nano
cmake --build --preset Release

cmake --preset Debug          # ATfE clang (-Og)
cmake --build --preset Debug

cmake --preset gcc-Release    # arm-none-eabi-gcc (-Os)
cmake --build --preset gcc-Release
```

Each build produces `c6t6.elf`, `c6t6.map`, `c6t6.hex` and `c6t6.bin` in
`build/<preset>/`. Flash the `.hex`, or the `.bin` at `0x08000000`.

On Windows, create the two local presets documented in
[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md#cmake-找不到工具链). VS Code
then presents only **开发调试 (Debug)** and **正式发布 (Release)**. They build to
`build/Debug/` and `build/Release/`, matching the checked-in clangd and
IntelliSense compilation-database paths. Use `local-Debug` for ordinary work
and `local-Release` for an optimized image.

Toolchain locations are discovered from `PATH`, a CMake cache variable, or an
environment variable. No developer-specific path is built into the project:

```sh
cmake -DSTARM_TOOLCHAIN_PATH=/opt/ATfE/bin \
      -DGNU_TOOLCHAIN_ROOT=/opt/gcc-arm-none-eabi \
      --preset Release
```

For the GCC presets, `arm-none-eabi-*` must be on `PATH`, or pass
`-DTOOLCHAIN_PREFIX=/path/to/bin/arm-none-eabi-`.

### EIDE

The `.eide` project uses the LLVM_ARM toolchain. Its source set includes
`Core`, the required HAL/LL drivers, `USB_DEVICE`, and the ST USB Device CDC
middleware. The obsolete UART HAL source is excluded. Open the repository in
EIDE and build the `Debug` target.

### Keil MDK-ARM

Open `MDK-ARM/c6t6.uvprojx` in µVision and build the `c6t6` target. The checked-in
project targets STM32F103C6 and ARM Compiler 6.24 (ArmClang), and includes the
same application, HAL/LL, USB Device and CDC middleware sources as the CMake
build. Install the STM32F1 Device Family Pack and CMSIS 6.3.0 pack if they are
not already available. Legacy ARM Compiler 5 support is not required by the
checked-in project.
Generated target output (`MDK-ARM/c6t6/`), listings and per-user µVision state
are intentionally ignored.

### Windows host application

The `host_app` directory contains a PySide6 desktop application for connecting
to the bridge, viewing and filtering CAN traffic, sending frames, polling the
device counters, and exporting CSV captures. Run it from source with:

```powershell
cd host_app
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Build the single-file Windows application with `host_app/build_exe.ps1`.

### Linux host application

The same PySide6 application runs on Linux with `/dev/ttyUSB*` and
`/dev/ttyACM*` devices. Build the executable and `linux-x64`/`linux-arm64`
tarball with `bash host_app/build_linux.sh`. Runtime libraries, serial-port
permissions and package compatibility are documented in
[`host_app/README.md`](host_app/README.md).

### Measured footprint

| Build | text | data | bss | flash | RAM |
|---|---|---|---|---|---|
| gcc-Release (`-Os`) | 19368 | 468 | 5668 | 19836 B (60.53%) | 6128 B (59.84%) |

This row is from the native USB prototype's local GCC release build. ATfE/EIDE
and MDK use different runtime libraries, so their exact sizes should be read
from their own build reports.

## Tests

The pure-logic modules (`Core/Src/can_bitrate.c`, `Core/Src/can_codec.c`,
`Core/Inc/ringbuf.h`) have
host-side unit tests that run on the development machine with an ordinary C
compiler:

```sh
powershell -NoProfile -ExecutionPolicy Bypass -File tools/run-host-tests.ps1
```

`tools/verify-build.ps1` is a standalone ARM rebuild used to validate changes
without Ninja; it mirrors `cmake/starm-clang.cmake` and additionally asserts
that every ELF LOAD segment sits at a low file offset (see the linker script
note below).

## Implementation notes

Defects fixed here, worth not regressing:

- **DLC and frame-length validation.** The data-copy loop used to be bounded by
  the DLC taken straight off the wire, so a 5-character frame such as `t1239`
  wrote `can_tx_data[8]` and clobbered the adjacent `can_rx_data` buffer. All
  bounds are now enforced in `can_decode()` before any byte is copied.

- **USB receive buffering.** The CDC receive callback feeds complete bytes into
  the existing line parser and command queue, then immediately rearms the OUT
  endpoint. Commands may use either `\r` or `\n` terminators.

- **USB transmit buffering.** CAN callbacks and command handling append output
  to a 512-byte ring. The main loop starts one CDC IN transfer at a time and
  removes data only after the class driver accepts it, so a busy endpoint does
  not block CAN interrupt handling.

- **Shared USB/CAN interrupt.** On STM32F103, USB low priority and CAN RX FIFO0
  share `USB_LP_CAN1_RX0_IRQn`. The handler services both the PCD and CAN HAL
  paths so neither peripheral loses its interrupt source.

- **CAN bus-off recovery.** With `AutoBusOff` disabled and no recovery logic,
  the node went permanently silent after a bus fault. `CAN_ServiceErrors()` now
  detects bus-off, restarts the controller and reprograms the filter banks
  (which `HAL_CAN_Stop()` deactivates).

- **Runtime CAN bit rate changes.** The `S0`..`S8` path stops the controller,
  re-enters bxCAN initialization through the HAL, restores filters and
  notifications, and rolls the previous timing back if the new start fails.

- **Non-blocking activity LED.** CAN callbacks only set an activity request
  flag. The main loop drives active-low PC13 and extends the pulse for 35 ms
  using `HAL_GetTick()`; it never calls `HAL_Delay()`. Repeated traffic extends
  the pulse, so the LED appears continuously on at high frame rates.

- **Linker script.** The `.data` load region had no controlled file offset, so
  `objcopy -O binary` emitted a ~400 MB image. `.got`/`.got.plt` are now part
  of the `.data` image and `._user_heap_stack` carries an explicit load region,
  which brings the binary down to its real size. `verify-build.ps1` checks it.

- **SWJ.** `__HAL_AFIO_REMAP_SWJ_DISABLE()` in `HAL_MspInit` removes the only
  debug transport on an LQFP48 F103C6, leaving no way to re-flash short of a
  full erase. It is now `__HAL_AFIO_REMAP_SWJ_NOJTAG()`, which keeps SWD.
  `c6t6.ioc` has been updated to match (SYS debug is `Serial Wire`, i.e. PA13 =
  `SYS_JTMS-SWDIO` and PA14 = `SYS_JTCK-SWCLK`), so regenerating from CubeMX
  reproduces the SWD-safe `HAL_MspInit` rather than the old `SWJ_DISABLE` one.
