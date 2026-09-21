# 板载 USB-CAN 实验报告

## 结论

STM32F103C6T6 的片上 USB 与 bxCAN 共用 512 字节专用 SRAM，不能同时运行。因此本板不能通过固件变成 USB-CAN 转换器；CDC、`gs_usb` 或 PCAN 协议都无法绕过这项硬件限制。

ST 的 [RM0008 参考手册](https://www.st.com/resource/en/reference_manual/rm0008-stm32f103xx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf)在 bxCAN 章节明确说明，低密度、中密度、高密度和 XL 密度 STM32F103 的 USB 与 CAN 共享专用 SRAM，二者只能分时使用。[AN4879 USB 硬件指南](https://www.st.com/resource/en/application_note/an4879-usb-hardware-design-guidelines-for-stm32-microcontrollers-stmicroelectronics.pdf)也在 STM32F102/F103 的 USB 缓冲区说明中记录了相同限制。

## 为什么改到 PB8/PB9 也不行

CAN1 remap 2 把 CAN_RX/CAN_TX 从 PA11/PA12 移到 PB8/PB9，确实释放了 USB D-/D+ 引脚，但这只解决封装引脚复用。USB 控制器和 bxCAN 控制器内部仍访问同一块 512 字节 SRAM。

一个 USB-CAN 桥必须同时保持 USB 枚举并实时收发 CAN。分时关闭一个外设再打开另一个外设无法完成桥接。

## 实板排查证据

测试环境：

- STM32F103C6T6，设备 ID `0x412`，32 KiB Flash、10 KiB RAM
- 8 MHz 外部晶振，SYSCLK 72 MHz，USB 时钟 48 MHz
- CMSIS-DAP + OpenOCD SWD 调试
- Windows USB 主机
- CubeMX USB Device CDC 中间件

同时启用 CAN 与 USB 时：

1. Windows 检测到全速 USB 上拉，但枚举为 `USB\VID_0000&PID_0002`，问题代码 43。
2. USB 总线复位已经到达 MCU，D+/D- 线状态和 USB 时钟正常。
3. 主机的第一个 SETUP 包触发 `HAL_PCD_SetupStageCallback()`。
4. EP0 OUT 结构配置为 PMA `0x18`，EP0 IN 配置为 PMA `0x58`，但 PMA 缓冲区描述表、SETUP 长度和数据均读回 0。
5. 因为 MCU 无法取得 `GET_DESCRIPTOR` 请求，控制 IN 阶段从未完成，Windows 最终报告设备描述符失败。

随后用同一份 USB 固件停用并反初始化 CAN：

1. USB PMA 恢复工作。
2. 代码 43 消失。
3. Windows 正常识别 `USB\VID_0483&PID_5740`。
4. CDC ACM 串口成功出现为 COM5。

这项对照测试证明 USB 接口、USB 线、D+ 上拉、时钟、描述符和 CDC 驱动本身都正常。

## PCAN 的含义

PCAN-View 和 PCAN-Basic 面向 PEAK 设备协议及其驱动。把 USB VID/PID 或产品字符串改成 PEAK 的值并不能实现 PCAN，并且不应冒用第三方设备标识。

如果诉求只是让电脑通过板载 USB 访问 CAN，可在支持 USB/CAN 并发的新 MCU 上实现 CDC 文本协议或公开的 `gs_usb`。如果必须兼容 PCAN 软件，需要先取得 PEAK 提供的公开协议、驱动接口与标识授权。

## 后续硬件选择

- 保持现有 STM32F103C6T6：使用外置 USB-UART，运行主分支固件。
- 更换 MCU：选择数据手册明确支持 USB 和 CAN 并发、Flash/RAM 足够且封装适合板卡的型号，再重新核对引脚和时钟。
- 增加独立控制器：保留 STM32F103，把 USB 或 CAN 功能放到另一颗芯片。

在确定新 MCU 前，不应继续为此分支实现 PCAN 或 `gs_usb`，因为协议层代码无法修复共享 SRAM 限制。
