# UART-CAN 上位机

适用于本仓库 STM32F103 UART-CAN 固件的 Windows 桌面工具。

![上位机界面](../docs/images/host-app.png)

第一次接线和烧录请从仓库根目录的[五分钟快速开始](../docs/QUICK_START.md)开始。

## 功能

- 扫描并连接 Windows COM 串口（固件默认 `115200 8N1`）
- 查询并切换设备 CAN 波特率（10 kbit/s～1 Mbit/s 的 9 个常用档位）
- 实时显示标准帧、扩展帧、数据帧和远程帧
- 按 CAN ID、收发方向和帧类型过滤
- 任务式发送 CAN 报文：可设置每次帧数、每次间隔和发送次数，第一批立即发送
- 可选 CAN ID 每帧 `+1`，以及数据整体按大端整数每帧 `+1`，并可随时停止
- 每秒读取固件 `V` 状态计数器
- 将当前过滤结果导出为 UTF-8 CSV
- 最多保留最近 20,000 条报文

“每次帧数”是一批中连续写入的帧数，“发送次数”是批次数，因此总帧数 = 每次帧数 × 发送次数。只发一帧时把两者都设为 `1`；周期发送时将“发送次数”设为期望值。

递增在每帧成功加入串口队列后生效。标准 ID 在 `0x7FF` 后回到 `0`，扩展 ID 在 `0x1FFFFFFF` 后回到 `0`；数据保持当前 DLC 宽度，例如 `00 FF → 01 00`，全 `FF` 后回到全 `00`。远程帧不递增数据。`1 ms` 是 Windows 定时调度目标，最大实际速度仍受操作系统和 UART 带宽限制。

## 源码运行

```powershell
cd host_app
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## 构建 Windows EXE

```powershell
.\host_app\build_exe.ps1
```

生成文件：`host_app/dist/UART-CAN-Host.exe`。

发布版本应运行 `tools/package-release.ps1`，由脚本重命名 EXE、配套固件并生成 SHA-256 校验文件。不要将 `dist/` 直接提交到 Git。

## 串口协议

应用使用固件现有的 SLCAN-like 文本协议，每条命令以 `\r` 结束：

- 标准数据帧：`tIIILDD...`
- 扩展数据帧：`TIIIIIIIILDD...`
- 远程帧：`r` / `R`
- 状态查询：`V`
- CAN 波特率查询：`S?`
- CAN 波特率设置：`S0`～`S8`

CAN 上电默认为 500 kbit/s，运行时可从界面修改；设备复位后恢复默认值。UART 固定为 115200 baud。
