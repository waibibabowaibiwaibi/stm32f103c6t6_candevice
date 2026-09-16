from __future__ import annotations

import os
from contextlib import nullcontext
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

SMOKE_TEST = "--smoke-test" in sys.argv
if SMOKE_TEST:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication

from canbridge.main_window import MainWindow, configure_application


def main() -> int:
    # Smoke checks should not replace the user's saved window or theme settings.
    with TemporaryDirectory(prefix="uart-can-smoke-") if SMOKE_TEST else nullcontext() as config_directory:
        app = QApplication(sys.argv)
        settings = (
            QSettings(str(Path(config_directory) / "settings.ini"), QSettings.IniFormat)
            if config_directory else None
        )
        configure_application(app, settings)
        window = MainWindow(settings=settings)
        window.show()
        if SMOKE_TEST:
            QTimer.singleShot(250, app.quit)
        return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
