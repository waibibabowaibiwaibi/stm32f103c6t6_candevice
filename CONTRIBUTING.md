# 参与贡献

感谢你愿意改进 UART-CAN Bridge。小修复可以直接提交 Pull Request；较大的协议或硬件变更，建议先开 Issue 说明使用场景，避免双方重复劳动。

## 提交问题

请尽量包含：

- MCU 板、CAN 收发器、USB-UART 和下载器型号
- 操作系统、Python、EIDE/CMake 和工具链版本
- CAN 总线波特率、节点数量与终端电阻情况
- 可复现步骤、期望结果、实际结果和完整错误输出
- 若涉及报文，提供脱敏后的原始串口文本或 CSV

不要上传车辆识别信息、客户报文、密钥或其他敏感总线数据。

## 开发检查

提交前至少运行与你改动相关的检查：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/run-host-tests.ps1

cd host_app
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py --smoke-test
```

修改固件时，再执行：

```powershell
cmake --preset gcc-Release
cmake --build --preset gcc-Release
```

涉及串口协议的变更必须同时更新 `docs/PROTOCOL.md`、固件解析测试和上位机协议测试。不要提交 `build/`、`host_app/dist/`、虚拟环境或本机工具链路径。

## 代码风格

- C 代码遵循仓库 `.clang-format`
- Python 使用类型标注并保持协议逻辑可单元测试
- 文档示例中的 CAN ID 与数据使用大写十六进制
- 保留 STM32CubeMX `USER CODE` 区域，确保重新生成代码后修改不会丢失

提交 Pull Request 时，请说明已执行的测试；如果某项无法测试，也请明确写出原因。
