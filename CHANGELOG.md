# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/)；正式发布前的变更记录在这里。

## [Unreleased]

### Added

- Linux 上位机可执行文件、带许可证与 SHA-256 的 tar.gz 打包脚本，以及 Windows/Linux CI 构建
- 亮色主题，默认跟随系统亮暗并即时切换；可手动选择亮色或暗色并保存设置
- Linux 中文字体适配、串口权限提示和伪终端串口读写测试

### Changed

- USART1 固件波特率与上位机默认波特率提高至 `921600 8N1`，同步 CubeMX 配置与使用文档
- Windows CMake Tools 只显示本机可用的调试与发布预设，Linux / CI 继续使用共享 GCC/Clang 预设
- 重新生成亮色与暗色上位机截图，并同步跨平台构建、发布说明和问题模板
- Keil MDK-ARM 工程迁移到 ARM Compiler 6.24（ArmClang）和 CMSIS 6.3.0
- 原生 USB-CAN 实验确认受 STM32F103 USB/bxCAN 共享 SRAM 限制，现有硬件继续采用外置 USB-UART

### Fixed

- ATfE/Clang 混合构建显式选择 Cortex-M3 Thumb multilib，避免 Release 镜像链接 ARM 状态运行库并在启动时 HardFault

## [0.1.0-beta] - 2026-09-14

### Added

- STM32F103C6T6 UART ↔ CAN 固件
- 经典 CAN 标准帧、扩展帧、数据帧与远程帧支持
- `V` 状态计数器命令
- PySide6 Windows 上位机、筛选、任务式发送和 CSV 导出
- 上位机和串口协议支持查询、切换 10 / 20 / 50 / 100 / 125 / 250 / 500 / 800 / 1000 kbit/s CAN 波特率
- Keil MDK-ARM / µVision 工程
- PC13 非阻塞 CAN 收发活动指示，单次活动脉冲约 35 ms
- 任务式发送支持每批帧数、间隔、发送次数、手动停止，以及 CAN ID/大端数据计数器逐帧递增
- C 固件逻辑测试、Python 上位机测试和 GitHub Actions

### Changed

- 文档明确 SN65HVD230 只是实测收发器，其他满足电气与协议条件的经典高速 CAN 收发器也可使用
- 明确当前硬件与固件不支持 CAN FD
- 发送按钮启动独立任务并立即发送第一批；使用精确单次定时器调度后续批次
- 串口发送队列增加容量上限和分批排空，避免高速发送占满内存或阻塞接收处理

### Fixed

- DLC/帧长越界检查
- UART overrun 恢复、接收队列与发送短写处理
- CAN bus-off 自动恢复
- 链接脚本生成异常大 BIN 的问题
- 保留 SWD 并避免 EIDE/Clang 的 `__aeabi_read_tp` 重复定义

### Verification pending

- 在真实 CAN 总线上验证除 250 kbit/s 外的其他波特率。
- 在真实串口设备上长时间验证高频批量发送。
