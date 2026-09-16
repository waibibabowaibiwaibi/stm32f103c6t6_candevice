from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QColor, QPalette  # noqa: E402
from PySide6.QtTest import QSignalSpy  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from canbridge.frame_model import FrameRecord, FrameTableModel  # noqa: E402
from canbridge.main_window import MainWindow  # noqa: E402
from canbridge.protocol import CanFrame  # noqa: E402
from canbridge.theme import COLORS, ThemeController  # noqa: E402


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.settings = QSettings(str(Path(self.directory.name) / "settings.ini"), QSettings.IniFormat)
        self.controller = ThemeController(self.app, self.settings)

    def tearDown(self) -> None:
        self.controller.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.directory.cleanup()

    def system_changes_to(self, scheme: Qt.ColorScheme) -> None:
        # Exercise the same Qt signal that native desktop appearance changes emit.
        self.app.styleHints().colorSchemeChanged.emit(scheme)
        self.app.processEvents()

    def test_system_mode_follows_live_changes_in_both_directions(self) -> None:
        self.assertEqual(self.controller.mode, "system")
        for scheme, theme in ((Qt.ColorScheme.Dark, "dark"), (Qt.ColorScheme.Light, "light")):
            self.system_changes_to(scheme)
            self.assertEqual(self.controller.theme, theme)
            self.assertEqual(self.app.palette().color(QPalette.Window), QColor(COLORS[theme]["window"]))
            self.assertIn(COLORS[theme]["base"], self.app.styleSheet())

    def test_manual_mode_persists_and_return_to_system_uses_latest_scheme(self) -> None:
        self.controller.set_mode("light")
        self.system_changes_to(Qt.ColorScheme.Dark)
        self.assertEqual(self.controller.theme, "light")
        self.assertEqual(self.settings.value("appearance/theme"), "light")
        restored = ThemeController(self.app, self.settings)
        self.assertEqual(restored.mode, "light")
        self.assertEqual(restored.theme, "light")
        restored.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.controller.set_mode("system")
        self.assertEqual(self.controller.theme, "dark")
        self.controller.set_mode("dark")
        self.system_changes_to(Qt.ColorScheme.Light)
        self.assertEqual(self.controller.theme, "dark")
        self.controller.set_mode("system")
        self.assertEqual(self.controller.theme, "light")

    def test_unknown_system_preference_uses_light(self) -> None:
        self.system_changes_to(Qt.ColorScheme.Unknown)
        self.assertEqual(self.controller.theme, "light")

    def test_existing_frame_colors_update_without_losing_records(self) -> None:
        model = FrameTableModel()
        self.controller.theme_changed.connect(model.set_theme)
        model.set_theme(self.controller.theme)
        for sequence, direction in enumerate(("RX", "TX"), start=1):
            model.append_record(FrameRecord(sequence, datetime.now(), direction, CanFrame(0x123), "wire"))
        records = list(model.records)
        changed = QSignalSpy(model.dataChanged)
        for theme in ("dark", "light"):
            self.controller.set_mode(theme)
            for row, direction in enumerate(("rx", "tx")):
                self.assertEqual(model.data(model.index(row, 2), Qt.ForegroundRole), QColor(COLORS[theme][direction]))
        self.assertGreaterEqual(changed.count(), 1)
        self.assertEqual(model.records, records)

    def test_ui_theme_selection_saves_preference_and_keeps_send_timer_running(self) -> None:
        window = MainWindow(settings=self.settings, theme_controller=self.controller)
        worker = Mock()
        worker.queue_line.return_value = True
        try:
            window._worker = worker
            window._update_connection_ui(True)
            window.send_repeat_spin.setValue(100)
            window.send_interval_spin.setValue(10000)
            window._start_send_task()
            window.theme_combo.setCurrentIndex(window.theme_combo.findData("dark"))
            self.assertEqual(self.settings.value("appearance/theme"), "dark")
            self.assertEqual(self.controller.theme, "dark")
            self.assertTrue(window._periodic_timer.isActive())
            self.assertTrue(window._send_task_running)
            self.assertIs(window._worker, worker)
            self.assertEqual(worker.queue_line.call_count, 1)
            window.theme_combo.setCurrentIndex(window.theme_combo.findData("system"))
            self.system_changes_to(Qt.ColorScheme.Light)
            self.assertEqual(self.controller.theme, "light")
        finally:
            window._stop_send_task()
            window._worker = None
            window.close()


if __name__ == "__main__":
    unittest.main()
