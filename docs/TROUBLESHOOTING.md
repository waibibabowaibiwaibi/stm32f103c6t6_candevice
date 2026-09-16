# 故障排查

建议按“电脑串口 → MCU 固件 → CAN 收发器 → 总线”的顺序检查，不要同时更换多个变量。

## 上位机找不到串口

- 本项目需要外部 USB-UART，STM32F103 固件本身不会枚举为 USB CDC 串口
- 检查 USB-UART 驱动和数据线；Windows 在设备管理器中确认 COM 号，Linux 用 `ls /dev/ttyUSB* /dev/ttyACM*` 确认设备
- 拔插设备后点击“刷新串口”
- 确认没有其他串口工具独占该端口

## Linux 串口权限或启动错误

- `Permission denied`：按[Linux 串口权限说明](../host_app/README.md#linux-串口权限)加入设备所属组（通常是 `dialout` 或 `uucp`），并重新登录
- `Could not load the Qt platform plugin "xcb"`：安装[上位机说明](../host_app/README.md#linux)中的系统运行库；可临时设置 `QT_DEBUG_PLUGINS=1` 查看缺失的库
- `GLIBC_x.y not found`：该程序在更新的发行版上构建；在当前系统从源码运行或重新构建
- 主题没有跟随系统：确认选择了“跟随系统”，并检查桌面的 `xdg-desktop-portal` 及对应后端是否正常；没有系统外观偏好时会使用亮色

## 可以打开串口，但状态计数器不刷新

- 波特率必须为 `921600 8N1`，无流控；若上位机保留了旧设置，请手动改为 `921600`
- USB-UART TXD 应接 PA10，RXD 应接 PA9，且必须共地
- 用普通串口工具发送 `V\r`，应收到 8 个数字组成的 `V ...` 回复
- 检查固件是否烧录到 `0x08000000` 并正常复位
- PC13 为低电平点亮的活动灯：收发时闪烁，高流量时可能常亮；没有流量却持续点亮通常表示固件进入致命错误处理

## 上位机显示 TX，但总线上没有报文

- `TX` 只说明命令进入串口，不代表 CAN 总线已 ACK
- PA12/PA11 必须先连接 CAN 收发器的 TXD/RXD，不能直接连接 CANH/CANL
- 检查收发器供电、使能/待机引脚和 3.3 V 逻辑兼容性
- 检查 CANH/CANL 是否接反、所有节点是否共地
- 查看上位机“设备 CAN”实际值，确保所有节点波特率一致；也可用串口发送 `S?\r` 查询
- 普通 CAN 模式通常需要至少一个正常工作的其他节点 ACK
- 断电测量 CANH 与 CANL：总线两端各 120 Ω 时通常约为 60 Ω
- 查看 `can_tx_drop` 和 `can_recover` 是否持续增加

## 上位机收不到其他节点的报文

- 先确认第二个节点与设备当前 CAN 波特率一致
- 检查 PA11 与收发器 RXD 的方向
- 确认收发器不是待机、静默或仅监听模式
- 使用示波器/逻辑分析仪分别检查 CANH/CANL 差分信号和收发器 RXD
- 查看 `can_recover`；持续增加通常代表位速率、接线或物理层存在问题

## 丢帧或错误计数增加

- `uart_drop`：上位机读取不够快或 CAN 流量超过 921600 串口在文本编码下的可承载范围
- `cmd_drop`：命令输入过快、行过长或固件命令队列已满
- `cmd_bad`：ID、DLC、数据长度或十六进制格式错误
- `can_tx_drop`：CAN 三个发送邮箱均忙，降低发送频率并检查总线 ACK
- `uart_err`：检查电平、电气噪声、共地和波特率
- `can_recover`：节点曾进入 bus-off，优先排查位速率、终端和接线

## EIDE 构建失败

- 确认选择的是 STM32F103C6T6 和 LLVM_ARM/当前项目配置
- EIDE 设备包位于本机 `.pack`，该目录不会提交到 Git；换电脑后需要由 EIDE 重新安装对应 pack
- 清理旧输出后重新构建，避免混用 GCC 与 Clang 目标文件
- 如果再次出现 `__aeabi_read_tp` 重复定义，确认 `Core/Src/syscalls.c` 中的兼容实现带有 `__attribute__((weak))`
- 仍失败时，请附完整链接命令和第一条 error，而不只是最后的“构建失败”提示

## Keil MDK-ARM 构建失败

- 打开 `MDK-ARM/c6t6.uvprojx`，目标器件应为 STM32F103C6
- 当前工程使用 ARM Compiler 5.06；新版 MDK 若未包含它，需要安装 Legacy Compiler Support，或在工程中迁移到已安装的编译器
- 确认已安装 STM32F1 Device Family Pack，且 `Core`、`Drivers` 相对路径没有失效
- 不要提交或依赖 `MDK-ARM/c6t6/`、`*.lst`、`*.uvguix.*` 等本机生成文件

## CMake 找不到工具链

GCC 构建要求 `arm-none-eabi-gcc` 位于 `PATH`，或显式指定前缀：

```powershell
cmake -DTOOLCHAIN_PREFIX=C:/toolchains/gcc-arm-none-eabi/bin/arm-none-eabi- --preset gcc-Release
```

ATfE/Clang 构建不包含任何开发者本机路径。请通过 CMake 参数或环境变量指定：

```powershell
cmake -DSTARM_TOOLCHAIN_PATH=C:/toolchains/ATfE/bin `
      -DGNU_TOOLCHAIN_ROOT=C:/toolchains/GNU-tools-for-STM32 `
      --preset Release
```

## Windows 拒绝运行上位机

当前测试版本没有代码签名。只从本项目 GitHub Release 下载，并先核对 `SHA256SUMS.txt`。如果仍不信任预编译文件，可以按 `host_app/README.md` 从源码运行或自行构建。

## 反馈问题

如果以上检查无效，请按仓库 Issue 模板提供硬件型号、接线、工具版本、错误计数和最小复现步骤。公开日志前先移除客户数据、车辆信息和其他敏感 CAN 报文。
