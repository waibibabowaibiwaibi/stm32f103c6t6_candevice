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
- 当前工程使用 ARM Compiler 6.24（ArmClang）和 CMSIS 6.3.0；确认对应编译器与 Pack 已安装，不需要 Legacy Compiler Support
- 确认已安装 STM32F1 Device Family Pack，且 `Core`、`Drivers` 相对路径没有失效
- 不要提交或依赖 `MDK-ARM/c6t6/`、`*.lst`、`*.uvguix.*` 等本机生成文件

## CMake 找不到工具链

Linux / CI 的 GCC 构建要求 `arm-none-eabi-gcc` 位于 `PATH`，或显式指定前缀：

```bash
cmake -DTOOLCHAIN_PREFIX=/opt/gcc-arm-none-eabi/bin/arm-none-eabi- --preset gcc-Release
```

Linux 的 ATfE/Clang 构建不包含任何开发者本机路径。请通过 CMake 参数或环境变量指定：

```bash
cmake -DSTARM_TOOLCHAIN_PATH=/opt/ATfE/bin \
      -DGNU_TOOLCHAIN_ROOT=/opt/gcc-arm-none-eabi \
      --preset Release
```

Windows 上的通用预设默认禁用，避免与本机预设重复显示；Linux 的命令行和 CI 仍使用原有通用预设。Windows 请把本机路径写进不被跟踪的 `CMakeUserPresets.json`（已加入 `.gitignore`），并用 `condition: true` 启用本机预设。日常只需调试和发布两项：

```json
{
  "version": 3,
  "configurePresets": [
    {
      "name": "local-Debug",
      "inherits": "Debug",
      "displayName": "开发调试 (Debug)",
      "condition": true,
      "binaryDir": "${sourceDir}/build/Debug",
      "cacheVariables": {
        "STARM_TOOLCHAIN_PATH": "<本机>/ATfE/bin",
        "GNU_TOOLCHAIN_ROOT": "<本机>/gcc-arm-none-eabi",
        "CMAKE_MAKE_PROGRAM": "<本机>/ninja"
      }
    },
    {
      "name": "local-Release",
      "inherits": "local-Debug",
      "displayName": "正式发布 (Release)",
      "binaryDir": "${sourceDir}/build/Release",
      "cacheVariables": { "CMAKE_BUILD_TYPE": "Release" }
    }
  ],
  "buildPresets": [
    { "name": "local-Debug", "configurePreset": "local-Debug" },
    { "name": "local-Release", "configurePreset": "local-Release" }
  ]
}
```

配置后执行 `cmake --preset local-Debug` 和 `cmake --build --preset local-Debug`；发布时把名称换成 `local-Release`。上面的 Windows 通用预设命令应相应使用本机预设。需要 GCC 时可创建继承 `gcc-Debug` 或 `gcc-Release` 的本机预设，设置 `condition: true` 和 `TOOLCHAIN_PREFIX`。

调试输出统一放在 `build/Debug`，与仓库 `.clangd` 和 IntelliSense 的编译数据库路径一致。切换配置后请重新运行 CMake 配置和构建，再重启 clangd。

## clangd 报 `'stdio.h' file not found`

- 本质是 clangd 服务器没有拿到 ATfE 自带 runtime 头文件（`lib/clang-runtimes/`）的搜索路径，与代码无关
- 仓库已在 `.vscode/settings.json` 和 `c6t6.code-workspace` 配置 `--query-driver=**/ATfE/bin/clang*`：无论插件用哪个 clangd（自动下载的官方版或 ATfE 自带版），都会查询工程使用的 ATfE clang 获取系统头文件路径
- 不要在共享配置里写 `--sysroot` 或本机编译器绝对路径：显式 `--sysroot` 会让 ATfE clang 不再搜索自带 runtime 头文件
- 想改用 ATfE 自带的 clangd（版本与固件工具链一致）时，在编辑器**用户设置**里配置 `clangd.path`，不要提交到仓库
- 自检：`clangd --check=Core/Src/main.c`，正常输出 `All checks completed, 0 errors`

## Windows 拒绝运行上位机

当前测试版本没有代码签名。只从本项目 GitHub Release 下载，并先核对 `SHA256SUMS.txt`。如果仍不信任预编译文件，可以按 `host_app/README.md` 从源码运行或自行构建。

## 反馈问题

如果以上检查无效，请按仓库 Issue 模板提供硬件型号、接线、工具版本、错误计数和最小复现步骤。公开日志前先移除客户数据、车辆信息和其他敏感 CAN 报文。
