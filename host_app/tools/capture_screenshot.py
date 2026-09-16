"""Create the README screenshot from the real Qt UI with representative data."""

from __future__ import annotations

import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HOST_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = HOST_ROOT.parent
sys.path.insert(0, str(HOST_ROOT))

from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from canbridge.frame_model import FrameRecord  # noqa: E402
from canbridge.main_window import MainWindow, configure_application  # noqa: E402
from canbridge.protocol import CanFrame  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", choices=("light", "dark"), default="dark")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "docs/images/host-app.png")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    windows_cjk_font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyh.ttc"
    if windows_cjk_font.exists():
        QFontDatabase.addApplicationFont(str(windows_cjk_font))
    with TemporaryDirectory(prefix="uart-can-screenshot-") as directory:
        settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.IniFormat)
        controller = configure_application(app, settings)
        controller.set_mode(args.theme)
        window = MainWindow(settings=settings)
        return capture(app, window, args.output)


def capture(app: QApplication, window: MainWindow, output: Path) -> int:

    window.port_combo.clear()
    port = "/dev/ttyUSB0" if sys.platform.startswith("linux") else "COM7"
    window.port_combo.addItem(f"{port} — USB Serial Port（演示）", port)
    window.connection_label.setText("● 已连接（演示）")
    window.connection_label.setObjectName("connected")
    window.connection_label.style().unpolish(window.connection_label)
    window.connection_label.style().polish(window.connection_label)
    window.can_bitrate_combo.setCurrentIndex(window.can_bitrate_combo.findData(500_000))
    window.can_bitrate_label.setText("设备 CAN：500 kbit/s（已生效）")
    window.can_bitrate_button.setEnabled(True)
    window.send_button.setEnabled(True)
    window.stop_send_button.setEnabled(False)
    window.frames_per_batch_spin.setValue(1)
    window.send_interval_spin.setValue(10)
    window.send_repeat_spin.setValue(10000)
    window.id_mode_combo.setCurrentText("递增")
    window.data_mode_combo.setCurrentText("递增")

    values = (1284, 96, 0, 0, 0, 0, 0, 0)
    for (key, _), value in zip(window.stat_values.items(), values, strict=True):
        window.stat_values[key].setText(str(value))

    started = datetime(2026, 9, 11, 12, 34, 56, 120000)
    examples = (
        ("RX", CanFrame(0x123, bytes.fromhex("11 22 33 44 55 66 77 88"))),
        ("TX", CanFrame(0x321, bytes.fromhex("DE AD BE EF"))),
        ("RX", CanFrame(0x18FF50E5, bytes.fromhex("01 7D 00 10"), extended=True)),
        ("RX", CanFrame(0x456, remote=True, dlc=8)),
        ("TX", CanFrame(0x7DF, bytes.fromhex("02 01 0C 00 00 00 00 00"))),
    )
    for sequence, (direction, frame) in enumerate(examples, start=1):
        window._frame_model.append_record(  # noqa: SLF001 - screenshot fixture
            FrameRecord(
                sequence=sequence,
                timestamp=started + timedelta(milliseconds=sequence * 37),
                direction=direction,
                frame=frame,
                wire_text="demo",
            )
        )

    window.resize(1280, 800)
    window.show()
    app.processEvents()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output), "PNG"):
        raise RuntimeError(f"Could not save screenshot to {output}")
    print(output)
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
