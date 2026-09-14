"""Qt table model and filters for captured CAN frames."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor

from .protocol import CanFrame


@dataclass(frozen=True, slots=True)
class FrameRecord:
    sequence: int
    timestamp: datetime
    direction: str
    frame: CanFrame
    wire_text: str


class FrameTableModel(QAbstractTableModel):
    HEADERS = ("序号", "时间", "方向", "类型", "CAN ID", "RTR", "DLC", "数据")

    def __init__(self, max_records: int = 20_000, parent=None) -> None:
        super().__init__(parent)
        self.records: list[FrameRecord] = []
        self.max_records = max_records

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.records)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.records):
            return None
        record = self.records[index.row()]
        frame = record.frame

        if role == Qt.DisplayRole:
            values = (
                record.sequence,
                record.timestamp.strftime("%H:%M:%S.%f")[:-3],
                record.direction,
                "扩展" if frame.extended else "标准",
                frame.id_text,
                "是" if frame.remote else "否",
                frame.dlc,
                frame.data_text if not frame.remote else "<REMOTE>",
            )
            return values[index.column()]
        if role == Qt.TextAlignmentRole:
            if index.column() in (0, 2, 3, 4, 5, 6):
                return Qt.AlignCenter
        if role == Qt.ForegroundRole and index.column() == 2:
            return QColor("#38bdf8" if record.direction == "RX" else "#fbbf24")
        if role == Qt.UserRole:
            return record
        return None

    def append_record(self, record: FrameRecord) -> None:
        if len(self.records) >= self.max_records:
            remove_count = min(max(1, self.max_records // 10), 500, len(self.records))
            self.beginRemoveRows(QModelIndex(), 0, remove_count - 1)
            del self.records[:remove_count]
            self.endRemoveRows()
        row = len(self.records)
        self.beginInsertRows(QModelIndex(), row, row)
        self.records.append(record)
        self.endInsertRows()

    def clear(self) -> None:
        if not self.records:
            return
        self.beginResetModel()
        self.records.clear()
        self.endResetModel()


class FrameFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._id_filter = ""
        self._direction = "全部"
        self._frame_type = "全部"
        self.setDynamicSortFilter(True)

    def set_filters(self, id_filter: str, direction: str, frame_type: str) -> None:
        modern_filter_api = hasattr(self, "beginFilterChange")
        if modern_filter_api:
            self.beginFilterChange()
        normalized = id_filter.strip().upper().removeprefix("0X")
        self._id_filter = normalized
        self._direction = direction
        self._frame_type = frame_type
        if modern_filter_api:
            self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        else:  # PySide 6.8 compatibility
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        model = self.sourceModel()
        if not isinstance(model, FrameTableModel):
            return True
        record = model.records[source_row]
        frame = record.frame
        if self._id_filter and self._id_filter not in frame.id_text:
            return False
        if self._direction != "全部" and record.direction != self._direction:
            return False
        if self._frame_type == "标准帧" and frame.extended:
            return False
        if self._frame_type == "扩展帧" and not frame.extended:
            return False
        if self._frame_type == "数据帧" and frame.remote:
            return False
        if self._frame_type == "远程帧" and not frame.remote:
            return False
        return True
