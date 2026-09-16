from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from canbridge.main_window import MainWindow  # noqa: E402


class DummyWorker:
    def __init__(self, *, accepts_lines: bool = True) -> None:
        self.lines: list[str] = []
        self.accepts_lines = accepts_lines

    def queue_line(self, line: str) -> bool:
        if not self.accepts_lines:
            return False
        self.lines.append(line)
        return True


class MainWindowSendTaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.settings_directory = TemporaryDirectory()
        settings = QSettings(str(Path(self.settings_directory.name) / "settings.ini"), QSettings.IniFormat)
        self.window = MainWindow(settings=settings)
        self.worker = DummyWorker()
        self.window._worker = self.worker  # noqa: SLF001 - isolated UI test double
        self.window._update_connection_ui(True)  # noqa: SLF001
        self.window.id_edit.setText("7FE")
        self.window.data_edit.setText("00 FF")
        self.window.send_interval_spin.setValue(20)

    def tearDown(self) -> None:
        self.window._stop_send_task()  # noqa: SLF001
        self.window._worker = None  # noqa: SLF001
        self.window.close()
        self.settings_directory.cleanup()

    def test_send_task_starts_immediately_and_repeats_requested_times(self) -> None:
        self.window.send_repeat_spin.setValue(3)

        self.window._start_send_task()  # noqa: SLF001

        self.assertEqual(self.worker.lines, ["t7FE200FF"])
        self.assertTrue(self.window._periodic_timer.isActive())  # noqa: SLF001
        QTest.qWait(80)
        self.assertEqual(self.worker.lines, ["t7FE200FF"] * 3)
        self.assertFalse(self.window._send_task_running)  # noqa: SLF001
        self.assertIn("已完成", self.window.send_progress_label.text())

    def test_batch_size_and_id_payload_increment_and_wrap(self) -> None:
        self.window.frames_per_batch_spin.setValue(2)
        self.window.id_mode_combo.setCurrentText("递增")
        self.window.data_mode_combo.setCurrentText("递增")

        self.window._start_send_task()  # noqa: SLF001

        self.assertEqual(self.worker.lines, ["t7FE200FF", "t7FF20100"])
        self.assertEqual(self.window.id_edit.text(), "000")
        self.assertEqual(self.window.data_edit.text(), "01 01")
        self.assertFalse(self.window._send_task_running)  # noqa: SLF001

    def test_stop_button_cancels_future_batches(self) -> None:
        self.window.send_repeat_spin.setValue(100)
        self.window._start_send_task()  # noqa: SLF001
        self.assertEqual(len(self.worker.lines), 1)

        self.window._stop_send_task()  # noqa: SLF001
        QTest.qWait(50)

        self.assertEqual(len(self.worker.lines), 1)
        self.assertFalse(self.window._periodic_timer.isActive())  # noqa: SLF001
        self.assertIn("手动停止", self.window.send_progress_label.text())

    def test_full_serial_queue_stops_task(self) -> None:
        self.worker.accepts_lines = False
        original_warning = QMessageBox.warning
        QMessageBox.warning = lambda *_args, **_kwargs: QMessageBox.StandardButton.Ok
        try:
            self.window._start_send_task()  # noqa: SLF001
        finally:
            QMessageBox.warning = original_warning

        self.assertFalse(self.window._send_task_running)  # noqa: SLF001
        self.assertIn("队列已满", self.window.send_progress_label.text())


if __name__ == "__main__":
    unittest.main()
