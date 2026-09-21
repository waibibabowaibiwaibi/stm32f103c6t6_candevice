# STM32F103 原生 USB-CAN 可行性验证

> [!WARNING]
> **验证结论：STM32F103C6T6 不能同时运行片上 USB 和 bxCAN，因此这颗 MCU 无法仅靠固件实现 USB-CAN、PCAN 兼容设备或 `gs_usb` 设备。这个实验分支不应合并为可用产品。**

ST 在 [RM0008 参考手册](https://www.st.com/resource/en/reference_manual/rm0008-stm32f103xx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf)中说明：STM32F103 的 USB 与 CAN 共用一块 512 字节专用 SRAM，二者不能并发使用。把 CAN 从 PA11/PA12 重映射到 PB8/PB9 只能解决引脚冲突，不能改变共享 SRAM 的硬件限制。

## 实板验证结果

本分支在 STM32F103C6T6 实板、8 MHz HSE 和 Windows 主机上完成了 SWD 级排查：

| 场景 | 结果 |
|---|---|
| USB 与 CAN 同时初始化 | Windows 报“设备描述符请求失败”，代码 43 |
| SWD 跟踪 USB 枚举 | 总线复位和第一个 SETUP 中断能到 MCU，但 USB PMA/缓冲区描述表读写为 0 |
| 停用并反初始化 CAN，只运行 USB | 立即正常枚举为 `VID_0483&PID_5740`，Windows 出现 CDC 串口 COM5 |
| 只使用主分支的 CAN + 外置 USB-UART | 保持原有可用架构 |

这组结果也排除了 USB 线序、D+ 上拉、48 MHz USB 时钟、描述符和 Windows 串口驱动。代码 43 的直接原因是 CAN 占用了 USB 所需的共享 SRAM。

详细断点证据和结论见[板载 USB 实验报告](docs/NATIVE_USB_PROTOTYPE.md)。

## 可行方案

现有硬件继续使用仓库 `main` 分支的架构：

```mermaid
flowchart LR
    PC[Windows / Linux 上位机] <-->|USB| UART[外置 USB-UART]
    UART <-->|USART| MCU[STM32F103C6T6]
    MCU <-->|CAN TX / RX| PHY[CAN 收发器]
    PHY <-->|CANH / CANL| BUS[经典 CAN 总线]
```

如果必须使用板载原生 USB，需要修改硬件：

- 换用明确支持 USB 与 CAN 并发的 MCU，并重新移植外设、时钟、链接脚本和工程配置。
- 保留 STM32F103，把 USB 或 CAN 其中一侧交给独立芯片。
- 继续使用外置 USB-UART，运行现有的串口 CAN 文本协议。

PCAN-View/PCAN-Basic 还要求 PEAK 的设备协议、驱动与合法设备标识。即使换了 MCU，也不能只替换 USB 描述符就成为 PCAN 设备。Linux 原生 SocketCAN 可以在合适的新 MCU 上考虑公开的 `gs_usb` 协议。

## 本分支中的构建修复

排查过程中还确认了 ATfE/Clang 混合工具链的独立问题：Clang 不会自动选择 GNU Arm 的 Cortex-M3 Thumb multilib。旧 Release 镜像会链接 ARM 状态的 Newlib 代码，并在 Cortex-M3 启动阶段触发 `UNDEFINSTR` HardFault。

本分支为编译和链接补齐 `-mthumb`，并通过 `arm-none-eabi-gcc -print-file-name` 显式定位 `thumb/v7-m/nofp` 运行库。该修复与 USB/CAN 共享 SRAM 限制相互独立。

## 推荐使用版本

请使用[主分支](https://github.com/waibibabowaibiwaibi/stm32f103c6t6_candevice/tree/main)的外置 USB-UART 固件。主分支的快速开始、协议、上位机与构建说明仍然适用于现有 STM32F103C6T6 硬件。
