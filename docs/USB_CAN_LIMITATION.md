# 板载 USB-CAN 实验报告

## 结论

STM32F103C6T6 的片上 USB 与 bxCAN 共用 512 字节专用 SRAM，不能同时运行。因此当前硬件不能仅通过修改固件变成 USB-CAN 转换器；USB CDC、`gs_usb` 或 PCAN 协议都无法绕过这项硬件限制。

ST 的 [RM0008 参考手册](https://www.st.com/resource/en/reference_manual/rm0008-stm32f103xx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf)在 bxCAN 章节说明，STM32F103 的 USB 与 CAN 共享专用 SRAM，二者只能分时使用。[AN4879 USB 硬件指南](https://www.st.com/resource/en/application_note/an4879-usb-hardware-design-guidelines-for-stm32-microcontrollers-stmicroelectronics.pdf)也记录了 STM32F102/F103 的 USB 缓冲区限制。

## 为什么改到 PB8/PB9 也不行

CAN1 remap 2 把 CAN_RX/CAN_TX 从 PA11/PA12 移到 PB8/PB9，可以释放 USB D-/D+ 引脚，但这只解决封装引脚复用。USB 控制器和 bxCAN 控制器内部仍访问同一块 512 字节 SRAM。

USB-CAN 桥必须同时保持 USB 枚举并实时收发 CAN。分时关闭一个外设再打开另一个外设无法完成桥接。

## 实板排查证据

测试环境：

- STM32F103C6T6，设备 ID `0x412`，32 KiB Flash、10 KiB RAM
- 8 MHz 外部晶振，SYSCLK 72 MHz，USB 时钟 48 MHz
- CMSIS-DAP + OpenOCD SWD 调试
- Windows USB 主机
- STM32Cube USB Device CDC 中间件

同时启用 CAN 与 USB 时：

1. Windows 检测到全速 USB 上拉，但枚举为 `USB\VID_0000&PID_0002`，问题代码 43。
2. USB 总线复位和主机的第一个 SETUP 包已经到达 MCU，D+/D- 线状态与 USB 时钟正常。
3. EP0 的 PMA 缓冲区描述表、SETUP 长度和数据均读回 0，MCU 无法取得 `GET_DESCRIPTOR` 请求。

随后用同一份 USB 固件停用并反初始化 CAN：

1. USB PMA 恢复工作，代码 43 消失。
2. Windows 正常识别 `USB\VID_0483&PID_5740`。
3. CDC ACM 串口成功枚举为 COM5。

这项对照测试排除了 USB 接口、数据线、D+ 上拉、48 MHz 时钟、描述符和 Windows 串口驱动问题。

## PCAN 兼容

PCAN-View 和 PCAN-Basic 使用 PEAK 的设备协议及驱动。只修改 USB VID/PID 或产品字符串不能实现 PCAN 兼容，也不应冒用第三方设备标识。

如果目标只是让电脑通过板载 USB 访问 CAN，可以在支持 USB 与 CAN 并发的新 MCU 上实现公开的 `gs_usb` 或本项目的 CDC 文本协议。如果必须兼容 PCAN 软件，还需要评估协议、驱动和设备标识的兼容与授权要求。

## 可行方案

- 保持现有 STM32F103C6T6：使用外置 USB-UART，运行主分支固件。
- 更换 MCU：选择数据手册明确支持 USB 与 CAN 并发、Flash/RAM 足够且封装合适的型号，再重新核对引脚和时钟。
- 增加独立控制器：保留 STM32F103，把 USB 或 CAN 功能放到另一颗芯片。
