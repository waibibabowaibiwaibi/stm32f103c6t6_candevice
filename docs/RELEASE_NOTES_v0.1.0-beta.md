# UART-CAN Bridge v0.1.0-beta

第一个公开测试版：把 STM32F103C6T6、USB-UART 和 CAN 收发器组合成一个带 Windows 图形上位机的简易 CAN 调试工具。

> “赵工把 CAN 盒拿走了，那我用什么？”
>
> 好消息：我们自己做了一个。

## 本版内容

- 经典 CAN 标准帧、扩展帧、数据帧和远程帧双向转换
- 上电默认 500 kbit/s CAN，可在上位机中切换 9 个常用波特率；UART 为 115200 8N1
- Windows 上位机实时显示、过滤、任务式批量/周期发送和 CSV 导出
- 发送任务支持停止、CAN ID 递增以及大端数据计数器递增
- 设备状态计数器、UART 错误恢复和 CAN bus-off 恢复
- PC13 非阻塞 CAN 收发活动指示
- EIDE、Keil MDK-ARM、ATfE/Clang CMake 与 GCC CMake 构建支持
- 固件逻辑测试、上位机测试和 GitHub Actions

## 下载

- `UART-CAN-Host-0.1.0-beta-windows-x64.exe`：Windows x64 上位机
- `c6t6-0.1.0-beta.hex`：推荐固件文件
- `c6t6-0.1.0-beta.bin`：从 `0x08000000` 烧录
- `SHA256SUMS.txt`：全部发布文件的 SHA-256
- 许可证与第三方声明文件：请与二进制一起保留

开始前请阅读仓库中的 `docs/QUICK_START.md`。PA11/PA12 不能直接连接 CANH/CANL，必须使用与 3.3 V MCU 逻辑兼容的 CAN 收发器。

## 已知限制

- 这是 beta 版，请先在实验台验证，不要用于安全关键控制
- CAN 波特率修改只在本次运行中生效，设备复位后恢复为 500 kbit/s
- 不支持 CAN FD
- 上位机 `TX` 只表示命令进入本机串口发送队列，不代表单片机已收到或总线已经 ACK
- 115200 UART 无法无损承载高负载 CAN 总线的全部峰值流量
- Windows EXE 尚未代码签名，下载后请核对 SHA-256

## 当前实测环境

- MCU：STM32F103C6T6，8 MHz 外部晶振
- CAN 收发器：SN65HVD230
- USB-UART：PowerWriter 串口设备，115200 8N1
- 下载器：CMSIS-DAP
- 已实测：250 kbit/s 下标准数据帧收发，以及 CAN ID/数据递增发送任务
- 待验收：其他波特率、扩展帧、远程帧、30 分钟连续运行和 bus-off 恢复

完成 `docs/RELEASE_CHECKLIST.md` 中剩余的硬件验收后，再将本文件内容粘贴到 GitHub Release 描述中。
