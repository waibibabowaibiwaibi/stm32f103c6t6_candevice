# 板载 USB-CAN 初稿

这个分支验证一条改动较小的路线：STM32F103C6T6 直接通过板载 USB 枚举为 CDC ACM 虚拟串口，继续承载仓库原有的 ASCII CAN 协议。现有上位机仍通过串口 API 工作，因此 Windows 和 Linux 端暂时不需要换一套协议实现。

## 接线变化

| 功能 | MCU 引脚 | 说明 |
|---|---|---|
| USB D- | PA11 | 连接板载 USB D- |
| USB D+ | PA12 | 连接板载 USB D+ |
| CAN RX | PB8 | 连接 CAN 收发器 RXD |
| CAN TX | PB9 | 连接 CAN 收发器 TXD |
| CAN 总线 | CANH / CANL | 必须经过 CAN 收发器 |

CAN1 使用 AFIO remap 2，从默认 PA11/PA12 移到 PB8/PB9。USB 使用 72 MHz PLL 除以 1.5 得到严格的 48 MHz 时钟。USB 低优先级中断和 CAN RX FIFO0 在 STM32F103 上共用 `USB_LP_CAN1_RX0_IRQn`，中断入口会依次调用 PCD 和 CAN HAL 处理函数。

## 当前能做什么

- 枚举为 USB CDC 虚拟串口。
- 继续解析原有 `t`、`T`、`r`、`R`、`S`、`V` 命令。
- 在 USB CDC 和经典 CAN 之间双向转发。
- 保留 CAN 波特率切换、bus-off 恢复和 PC13 活动灯。
- 使用同一套 CMake 工程在 Windows 本机和 Linux CI 构建。

## 这不是 PCAN

PCAN-View 和 PCAN-Basic 期望 PEAK 的设备协议、驱动配合及合法的设备标识。这个初稿不会冒充 PEAK 的 VID/PID，也没有复制其私有协议。它在操作系统里表现为普通串口，现有上位机可以直接连接。

若目标是 Linux 原生 SocketCAN，下一阶段更适合实现公开的 `gs_usb` 协议。若目标是让 PCAN-View 直接识别，则需要先确认 PEAK 是否提供可合法实现的开放设备协议和标识授权；在此之前不应把固件伪装成 PCAN 硬件。

## 验证步骤

1. 用 GCC 或 ATfE/Clang 构建并烧录 `c6t6.hex`。
2. 插入板载 USB，确认 Windows 出现新的 COM 口，或 Linux 出现 `/dev/ttyACM*`。
3. 在上位机选择该端口并连接。波特率字段可保持 `921600`，CDC 固件会接受该设置但不会据此改变 USB 速度。
4. 发送 `V\r`，应收到八个状态计数值。
5. 连接带正确终端电阻和另一 ACK 节点的 CAN 总线，再验证标准帧、扩展帧和远程帧双向收发。

## 初稿限制

- 尚未在目标板上验证 USB 枚举和长时间 CAN 压力测试。
- USB 描述符暂用 ST CDC 示例的 `0483:5740`，只适合开发验证；正式分发前要换成项目有权使用的 VID/PID。
- 常见 Blue Pill 类板子的 D+ 上拉电阻可能不符合 USB 规范，若无法枚举，需要先检查原理图和实物阻值。
- 该分支修改了引脚，原来接在 PA11/PA12 的 CAN 收发器必须改接 PB8/PB9。
