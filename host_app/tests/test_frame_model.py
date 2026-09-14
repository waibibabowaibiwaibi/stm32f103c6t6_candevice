from __future__ import annotations

import os
import unittest
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from canbridge.frame_model import (  # noqa: E402
    FrameFilterProxyModel,
    FrameRecord,
    FrameTableModel,
)
from canbridge.protocol import CanFrame  # noqa: E402


class FrameModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.model = FrameTableModel(max_records=3)
        self.proxy = FrameFilterProxyModel()
        self.proxy.setSourceModel(self.model)

    def append(self, sequence: int, direction: str, frame: CanFrame) -> None:
        self.model.append_record(
            FrameRecord(sequence, datetime(2026, 1, 1), direction, frame, "wire")
        )

    def test_model_keeps_only_configured_number_of_records(self) -> None:
        for sequence in range(1, 5):
            self.append(sequence, "RX", CanFrame(sequence))
        self.assertEqual(self.model.rowCount(), 3)
        self.assertEqual([item.sequence for item in self.model.records], [2, 3, 4])

    def test_filters_by_direction_and_id(self) -> None:
        self.append(1, "RX", CanFrame(0x123))
        self.append(2, "TX", CanFrame(0x321))
        self.proxy.set_filters("123", "RX", "全部")
        self.assertEqual(self.proxy.rowCount(), 1)

    def test_filters_by_frame_kind(self) -> None:
        self.append(1, "RX", CanFrame(0x123))
        self.append(2, "RX", CanFrame(0x123, extended=True))
        self.append(3, "RX", CanFrame(0x123, extended=True, remote=True, dlc=8))
        self.proxy.set_filters("", "全部", "扩展帧")
        self.assertEqual(self.proxy.rowCount(), 2)
        self.proxy.set_filters("", "全部", "远程帧")
        self.assertEqual(self.proxy.rowCount(), 1)


if __name__ == "__main__":
    unittest.main()

