from __future__ import annotations

import os
import sys

SMOKE_TEST = "--smoke-test" in sys.argv
if SMOKE_TEST:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from canbridge.main_window import MainWindow, configure_application


def main() -> int:
    app = QApplication(sys.argv)
    configure_application(app)
    window = MainWindow()
    window.show()
    if SMOKE_TEST:
        QTimer.singleShot(250, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
