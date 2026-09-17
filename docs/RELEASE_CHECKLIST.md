# Release 检查表

建议首个公开版本使用 `v0.1.0-beta`。只有完成真实硬件双向收发测试后再发布，不要仅凭软件单元测试将版本标记为 stable。

## 代码与文档

- [x] 根目录包含 README、MIT License 和第三方许可证说明
- [x] README 包含功能、接线、烧录、快速开始、限制和排障入口
- [x] 构建脚本不包含开发者用户名或固定本机工具链路径
- [x] 上位机 EXE、虚拟环境和构建目录不会提交到 Git
- [x] GitHub Actions 覆盖 GCC 固件构建、C 逻辑测试和 Python 测试
- [x] Release 打包脚本包含项目、固件依赖和上位机依赖的许可证说明
- [x] 检查当前快照与可达 Git 历史，确认没有密钥、客户报文、串口日志或无关文件

## 自动检查

- [x] `tools/run-host-tests.ps1` 的 3 个固件逻辑测试程序全部通过
- [x] `host_app` Python 测试全部通过（31 项）
- [x] 上位机源码 smoke test 通过
- [x] Linux GCC Release 固件构建通过：Flash 使用 13,236 B，RAM 区使用 2,952 B
- [x] 打包版 EXE smoke test 通过

## 硬件验收

- [x] 记录当前实测组合：STM32F103C6T6 / 8 MHz HSE、SN65HVD230、PowerWriter 串口设备、CMSIS-DAP
- [ ] 在 500 kbit/s、双 120 Ω 终端的实验总线上验证 UART → CAN
- [ ] 验证 CAN → UART，包括标准帧、扩展帧和远程帧
- [ ] 连续运行至少 30 分钟，无异常丢帧和串口错误增长
- [ ] 人为断开/恢复总线，确认 bus-off 恢复行为
- [ ] 检查收发器和 MCU 的逻辑电平、电源电压与温升

## GitHub 发布

1. 更新 `CHANGELOG.md` 的版本和日期。
2. 提交所有有意修改，并确保 CI 通过。
3. 在 Windows 运行：

   ```powershell
   .\tools\package-release.ps1 -Version v0.1.0-beta
   ```

4. 在 Ubuntu 22.04 x64 运行 `bash host_app/build_linux.sh`，或从成功的 GitHub Actions 下载 `UART-CAN-Host-linux-x64` artifact；取得 `.tar.gz` 和同名 `.sha256` 文件。
5. 检查 `release/v0.1.0-beta/` 中的 EXE、HEX、BIN、许可证材料和 `SHA256SUMS.txt`，并把 Linux `.tar.gz` 与 `.sha256` 一起列入 Release；如发布 Qt/PySide6 二进制，按所选 LGPL/GPL/商业授权方式完成合规复核。
6. 创建 annotated tag：`git tag -a v0.1.0-beta -m "UART-CAN Bridge v0.1.0-beta"`。
7. 推送分支和 tag，在 GitHub 创建 prerelease，并上传上述 Windows、Linux、固件和许可证文件。
8. 复核并粘贴 `docs/RELEASE_NOTES_v0.1.0-beta.md`，其中应包含实测硬件、可选 CAN 波特率、未签名 EXE、Linux 运行库提示和已知限制。
9. 发布后，分别在没有开发环境的 Windows 和 Linux 电脑上从 Release 下载并完整走一遍快速开始。
