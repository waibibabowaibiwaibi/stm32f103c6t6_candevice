"""Main window for the UART-CAN desktop application."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from serial.tools import list_ports

from .frame_model import FrameFilterProxyModel, FrameRecord, FrameTableModel
from .protocol import (
    CAN_BITRATES,
    CanBitrateStatus,
    CanFrame,
    DeviceError,
    DeviceStats,
    ProtocolError,
    advance_frame,
    decode_device_line,
    encode_bitrate_command,
    encode_frame,
    parse_data_bytes,
    parse_identifier,
)
from .serial_worker import SerialWorker


APP_STYLE = """
QMainWindow, QWidget { background: #0f172a; color: #e2e8f0; }
QGroupBox {
    border: 1px solid #334155; border-radius: 8px; margin-top: 12px;
    padding: 10px 8px 8px 8px; font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #93c5fd; }
QLineEdit, QComboBox, QSpinBox {
    background: #1e293b; border: 1px solid #475569; border-radius: 5px;
    padding: 6px; selection-background-color: #2563eb;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #38bdf8; }
QPushButton {
    background: #1e40af; border: 1px solid #3b82f6; border-radius: 5px;
    padding: 7px 14px; font-weight: 600;
}
QPushButton:hover { background: #2563eb; }
QPushButton:pressed { background: #1d4ed8; }
QPushButton:disabled { background: #334155; border-color: #475569; color: #94a3b8; }
QPushButton#dangerButton { background: #7f1d1d; border-color: #ef4444; }
QPushButton#quietButton { background: #1e293b; border-color: #475569; }
QTableView {
    background: #111827; alternate-background-color: #172033; border: 1px solid #334155;
    border-radius: 6px; gridline-color: #273449; selection-background-color: #1d4ed8;
}
QHeaderView::section {
    background: #1e293b; color: #cbd5e1; border: 0; border-right: 1px solid #334155;
    border-bottom: 1px solid #334155; padding: 7px; font-weight: 600;
}
QFrame#statCard { background: #111827; border: 1px solid #334155; border-radius: 7px; }
QLabel#statValue { color: #67e8f9; font-size: 17px; font-weight: 700; }
QLabel#muted { color: #94a3b8; }
QLabel#connected { color: #4ade80; font-weight: 700; }
QLabel#disconnected { color: #f87171; font-weight: 700; }
QStatusBar { background: #111827; color: #94a3b8; }
QSplitter::handle { background: #334155; height: 2px; }
"""


STAT_LABELS = (
    ("can_rx", "CAN 接收"),
    ("can_tx", "CAN 发送"),
    ("uart_drop", "UART 丢弃"),
    ("cmd_drop", "命令丢弃"),
    ("cmd_bad", "非法命令"),
    ("can_tx_drop", "发送丢弃"),
    ("uart_err", "UART 错误"),
    ("can_recover", "CAN 恢复"),
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("UART-CAN 上位机")
        self.setMinimumSize(1040, 680)
        self.resize(1280, 800)
        self.setWindowIcon(self._make_icon())

        self._settings = QSettings("CANDevice", "UART-CAN Host")
        self._worker: SerialWorker | None = None
        self._sequence = 0
        self._capture_paused = False
        self._received_lines = 0
        self._malformed_lines = 0
        self._send_task_running = False
        self._send_batches_total = 0
        self._send_batches_remaining = 0
        self._send_frames_sent = 0
        self._last_send_error = ""

        self._frame_model = FrameTableModel(parent=self)
        self._proxy_model = FrameFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._frame_model)

        self._periodic_timer = QTimer(self)
        self._periodic_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._periodic_timer.setSingleShot(True)
        self._periodic_timer.timeout.connect(self._send_next_batch)
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1000)
        self._status_timer.timeout.connect(self._request_status)

        self._build_ui()
        self._restore_settings()
        self._refresh_ports()
        self._update_connection_ui(False)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        root.addWidget(self._build_connection_panel())
        root.addLayout(self._build_stats_panel())

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._build_capture_panel())
        splitter.addWidget(self._build_transmit_panel())
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([520, 220])
        root.addWidget(splitter, 1)

        self.setCentralWidget(central)
        self.statusBar().showMessage("就绪")

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        self.addAction(exit_action)

    def _build_connection_panel(self) -> QGroupBox:
        group = QGroupBox("设备连接")
        layout = QGridLayout(group)

        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(260)
        self.refresh_button = QPushButton("刷新串口")
        self.refresh_button.setObjectName("quietButton")
        self.refresh_button.clicked.connect(self._refresh_ports)

        self.baud_combo = QComboBox()
        self.baud_combo.addItems(("9600", "57600", "115200", "230400", "460800", "921600"))
        self.baud_combo.setCurrentText("115200")

        self.can_bitrate_combo = QComboBox()
        for bitrate in CAN_BITRATES:
            self.can_bitrate_combo.addItem(f"{bitrate // 1000} kbit/s", bitrate)
        self.can_bitrate_combo.setCurrentIndex(self.can_bitrate_combo.findData(500_000))
        self.can_bitrate_button = QPushButton("应用 CAN 波特率")
        self.can_bitrate_button.setObjectName("quietButton")
        self.can_bitrate_button.clicked.connect(self._apply_can_bitrate)
        self.can_bitrate_label = QLabel("设备 CAN：未读取")
        self.can_bitrate_label.setObjectName("muted")

        self.connect_button = QPushButton("连接")
        self.connect_button.clicked.connect(self._toggle_connection)
        self.connection_label = QLabel("● 未连接")
        self.connection_label.setObjectName("disconnected")

        self.auto_status_checkbox = QCheckBox("每秒读取设备状态")
        self.auto_status_checkbox.setChecked(True)
        self.auto_status_checkbox.toggled.connect(self._update_status_polling)

        layout.addWidget(QLabel("串口"), 0, 0)
        layout.addWidget(self.port_combo, 0, 1)
        layout.addWidget(self.refresh_button, 0, 2)
        layout.addWidget(QLabel("UART 波特率"), 0, 3)
        layout.addWidget(self.baud_combo, 0, 4)
        layout.addWidget(self.connect_button, 0, 5)
        layout.addWidget(self.connection_label, 0, 6)
        layout.addWidget(self.auto_status_checkbox, 0, 7)
        layout.addWidget(QLabel("CAN 波特率"), 1, 0)
        layout.addWidget(self.can_bitrate_combo, 1, 1)
        layout.addWidget(self.can_bitrate_button, 1, 2)
        layout.addWidget(self.can_bitrate_label, 1, 3, 1, 5)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(6, 1)
        return group

    def _build_stats_panel(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(8)
        self.stat_values: dict[str, QLabel] = {}
        for key, title in STAT_LABELS:
            card = QFrame()
            card.setObjectName("statCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 7, 10, 7)
            title_label = QLabel(title)
            title_label.setObjectName("muted")
            value_label = QLabel("—")
            value_label.setObjectName("statValue")
            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)
            self.stat_values[key] = value_label
            layout.addWidget(card, 1)
        return layout

    def _build_capture_panel(self) -> QGroupBox:
        group = QGroupBox("CAN 报文")
        layout = QVBoxLayout(group)
        controls = QHBoxLayout()

        self.id_filter_edit = QLineEdit()
        self.id_filter_edit.setPlaceholderText("ID 过滤，如 123")
        self.id_filter_edit.setMaximumWidth(190)
        self.direction_filter = QComboBox()
        self.direction_filter.addItems(("全部", "RX", "TX"))
        self.type_filter = QComboBox()
        self.type_filter.addItems(("全部", "标准帧", "扩展帧", "数据帧", "远程帧"))
        self.pause_button = QPushButton("暂停显示")
        self.pause_button.setCheckable(True)
        self.pause_button.setObjectName("quietButton")
        self.pause_button.toggled.connect(self._set_capture_paused)
        self.clear_button = QPushButton("清空")
        self.clear_button.setObjectName("quietButton")
        self.clear_button.clicked.connect(self._clear_capture)
        self.export_button = QPushButton("导出 CSV")
        self.export_button.setObjectName("quietButton")
        self.export_button.clicked.connect(self._export_csv)

        self.id_filter_edit.textChanged.connect(self._apply_filters)
        self.direction_filter.currentTextChanged.connect(self._apply_filters)
        self.type_filter.currentTextChanged.connect(self._apply_filters)

        controls.addWidget(QLabel("过滤"))
        controls.addWidget(self.id_filter_edit)
        controls.addWidget(self.direction_filter)
        controls.addWidget(self.type_filter)
        controls.addStretch(1)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.clear_button)
        controls.addWidget(self.export_button)
        layout.addLayout(controls)

        self.frame_table = QTableView()
        self.frame_table.setModel(self._proxy_model)
        self.frame_table.setAlternatingRowColors(True)
        self.frame_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.frame_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.frame_table.setSortingEnabled(False)
        self.frame_table.verticalHeader().setVisible(False)
        self.frame_table.setWordWrap(False)
        self.frame_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.frame_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Stretch)
        layout.addWidget(self.frame_table, 1)
        return group

    def _build_transmit_panel(self) -> QGroupBox:
        group = QGroupBox("发送 CAN 报文")
        outer = QVBoxLayout(group)
        content_row = QHBoxLayout()

        format_form = QFormLayout()
        format_form.setHorizontalSpacing(10)
        self.frame_type_combo = QComboBox()
        self.frame_type_combo.addItems(("数据帧", "远程帧"))
        self.frame_type_combo.currentTextChanged.connect(self._update_remote_ui)
        format_form.addRow("帧类型", self.frame_type_combo)

        self.frame_kind_combo = QComboBox()
        self.frame_kind_combo.addItems(("标准帧", "扩展帧"))
        self.frame_kind_combo.currentTextChanged.connect(self._update_id_hint)
        format_form.addRow("帧格式", self.frame_kind_combo)

        self.dlc_spin = QSpinBox()
        self.dlc_spin.setRange(0, 8)
        self.dlc_spin.setValue(8)
        format_form.addRow("DLC", self.dlc_spin)
        content_row.addLayout(format_form)

        task_layout = QVBoxLayout()
        batch_row = QHBoxLayout()
        self.frames_per_batch_spin = QSpinBox()
        self.frames_per_batch_spin.setRange(1, 100)
        self.frames_per_batch_spin.setValue(1)
        self.send_interval_spin = QSpinBox()
        self.send_interval_spin.setRange(1, 3_600_000)
        self.send_interval_spin.setValue(1000)
        self.send_interval_spin.setSuffix(" ms")
        self.send_repeat_spin = QSpinBox()
        self.send_repeat_spin.setRange(1, 1_000_000)
        self.send_repeat_spin.setValue(1)
        batch_row.addWidget(QLabel("每次帧数"))
        batch_row.addWidget(self.frames_per_batch_spin)
        batch_row.addSpacing(10)
        batch_row.addWidget(QLabel("每次发送间隔"))
        batch_row.addWidget(self.send_interval_spin)
        batch_row.addSpacing(10)
        batch_row.addWidget(QLabel("发送次数"))
        batch_row.addWidget(self.send_repeat_spin)
        batch_row.addStretch(1)
        task_layout.addLayout(batch_row)

        id_row = QHBoxLayout()
        self.id_mode_combo = QComboBox()
        self.id_mode_combo.addItems(("固定", "递增"))
        self.id_mode_combo.setToolTip("递增时达到帧 ID 上限后回到 0")
        self.id_edit = QLineEdit("123")
        self.id_edit.setPlaceholderText("000–7FF")
        id_row.addWidget(QLabel("CAN ID（HEX）"))
        id_row.addWidget(self.id_mode_combo)
        id_row.addWidget(self.id_edit, 1)
        task_layout.addLayout(id_row)

        data_row = QHBoxLayout()
        self.data_mode_combo = QComboBox()
        self.data_mode_combo.addItems(("固定", "递增"))
        self.data_mode_combo.setToolTip("按大端整数递增，例如 00 FF → 01 00")
        self.data_edit = QLineEdit("00 00 00 00 00 00 00 00")
        self.data_edit.setPlaceholderText("例如：11 22 33 44")
        self.data_edit.setMinimumWidth(330)
        self.data_edit.textChanged.connect(self._sync_dlc_from_data)
        data_row.addWidget(QLabel("数据（HEX）"))
        data_row.addWidget(self.data_mode_combo)
        data_row.addWidget(self.data_edit, 1)
        task_layout.addLayout(data_row)
        content_row.addLayout(task_layout, 1)

        button_column = QVBoxLayout()
        self.send_button = QPushButton("发送")
        self.send_button.setMinimumSize(110, 48)
        self.send_button.clicked.connect(self._start_send_task)
        self.stop_send_button = QPushButton("停止")
        self.stop_send_button.setObjectName("quietButton")
        self.stop_send_button.setMinimumSize(110, 42)
        self.stop_send_button.clicked.connect(self._stop_send_task)
        button_column.addWidget(self.send_button)
        button_column.addWidget(self.stop_send_button)
        button_column.addStretch(1)
        content_row.addLayout(button_column)
        outer.addLayout(content_row)

        self.send_progress_label = QLabel("发送任务：未运行")
        self.send_progress_label.setObjectName("muted")
        outer.addWidget(self.send_progress_label)

        hint = QLabel(
            "总帧数 = 每次帧数 × 发送次数；第一批立即发送。"
            "1 ms 为调度目标，实际速度受 Windows 与 115200 UART 限制。TX 不代表 CAN 总线 ACK。"
        )
        hint.setObjectName("muted")
        outer.addWidget(hint)
        return group

    def _refresh_ports(self) -> None:
        current_device = self.port_combo.currentData()
        saved_device = self._settings.value("serial/port", "", type=str)
        ports = sorted(list_ports.comports(), key=lambda item: item.device)
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        for port in ports:
            description = port.description if port.description and port.description != "n/a" else "串口设备"
            self.port_combo.addItem(f"{port.device} — {description}", port.device)
        wanted = current_device or saved_device
        if wanted:
            for index in range(self.port_combo.count()):
                if self.port_combo.itemData(index) == wanted:
                    self.port_combo.setCurrentIndex(index)
                    break
        self.port_combo.blockSignals(False)
        if not ports:
            self.port_combo.addItem("未发现串口", None)

    def _toggle_connection(self) -> None:
        if self._worker is not None:
            self._disconnect_serial()
        else:
            self._connect_serial()

    def _connect_serial(self) -> None:
        port = self.port_combo.currentData()
        if not port:
            QMessageBox.warning(self, "没有串口", "请连接设备并点击“刷新串口”。")
            return
        baudrate = int(self.baud_combo.currentText())
        self._settings.setValue("serial/port", port)
        self._settings.setValue("serial/baudrate", baudrate)
        worker = SerialWorker(port, baudrate, self)
        worker.line_received.connect(self._handle_device_line)
        worker.port_opened.connect(self._on_port_opened)
        worker.port_closed.connect(self._on_port_closed)
        worker.io_error.connect(self._on_io_error)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        self.connect_button.setEnabled(False)
        self.connection_label.setText("● 正在连接…")
        worker.start()

    def _disconnect_serial(self) -> None:
        worker = self._worker
        if worker is None:
            return
        self.connect_button.setEnabled(False)
        self.connection_label.setText("● 正在断开…")
        if self._send_task_running:
            self._finish_send_task("发送任务：串口正在断开")
        self._status_timer.stop()
        worker.request_stop()

    def _on_port_opened(self, port: str) -> None:
        self._update_connection_ui(True)
        self.connection_label.setText(f"● 已连接 {port}")
        self.statusBar().showMessage(f"已连接 {port}，设备 UART 应设置为 115200 8N1")
        self._update_status_polling()
        QTimer.singleShot(120, self._request_status)
        QTimer.singleShot(220, self._request_can_bitrate)

    def _on_port_closed(self) -> None:
        self._worker = None
        self._update_connection_ui(False)
        self.statusBar().showMessage("串口已断开")

    def _on_io_error(self, message: str) -> None:
        self.statusBar().showMessage(f"串口错误：{message}")
        if not message.startswith("收到超过"):
            QMessageBox.critical(self, "串口错误", message)

    def _update_connection_ui(self, connected: bool) -> None:
        self.port_combo.setEnabled(not connected)
        self.baud_combo.setEnabled(not connected)
        self.refresh_button.setEnabled(not connected)
        self.can_bitrate_button.setEnabled(connected)
        self.connect_button.setEnabled(True)
        self.connect_button.setText("断开" if connected else "连接")
        self.connect_button.setObjectName("dangerButton" if connected else "")
        self.connect_button.style().unpolish(self.connect_button)
        self.connect_button.style().polish(self.connect_button)
        if not connected:
            self.connection_label.setText("● 未连接")
            self.connection_label.setObjectName("disconnected")
            if self._send_task_running:
                self._finish_send_task("发送任务：串口已断开")
            self._status_timer.stop()
            self.can_bitrate_label.setText("设备 CAN：未读取")
            for label in self.stat_values.values():
                label.setText("—")
        else:
            self.connection_label.setObjectName("connected")
        self.connection_label.style().unpolish(self.connection_label)
        self.connection_label.style().polish(self.connection_label)
        self.send_button.setEnabled(connected and not self._send_task_running)
        self.stop_send_button.setEnabled(connected and self._send_task_running)

    def _handle_device_line(self, line: str) -> None:
        self._received_lines += 1
        try:
            decoded = decode_device_line(line)
        except ProtocolError:
            self._malformed_lines += 1
            self.statusBar().showMessage(
                f"收到无法解析的数据：{line!r}（异常行 {self._malformed_lines}）"
            )
            return

        if isinstance(decoded, DeviceStats):
            self._update_stats(decoded)
            return
        if isinstance(decoded, CanBitrateStatus):
            index = self.can_bitrate_combo.findData(decoded.bitrate)
            if index >= 0:
                self.can_bitrate_combo.setCurrentIndex(index)
            self.can_bitrate_label.setText(f"设备 CAN：{decoded.bitrate // 1000} kbit/s（已生效）")
            self._settings.setValue("can/bitrate", decoded.bitrate)
            self.statusBar().showMessage(f"CAN 波特率为 {decoded.bitrate // 1000} kbit/s")
            return
        if isinstance(decoded, DeviceError):
            if decoded.command == "S":
                self.can_bitrate_label.setText("设备 CAN：设置失败，已保留原值")
                self.statusBar().showMessage("CAN 波特率设置失败；固件已尝试回滚原配置")
                QTimer.singleShot(100, self._request_can_bitrate)
            else:
                self.statusBar().showMessage(f"设备报告命令错误：{decoded.command}")
            return
        if not self._capture_paused:
            self._append_frame("RX", decoded, line)

    def _append_frame(self, direction: str, frame: CanFrame, wire_text: str) -> None:
        self._sequence += 1
        record = FrameRecord(
            sequence=self._sequence,
            timestamp=datetime.now(),
            direction=direction,
            frame=frame,
            wire_text=wire_text.rstrip("\r\n"),
        )
        self._frame_model.append_record(record)
        if self.frame_table.verticalScrollBar().value() >= self.frame_table.verticalScrollBar().maximum() - 2:
            self.frame_table.scrollToBottom()
        self._show_capture_count()

    def _update_stats(self, stats: DeviceStats) -> None:
        for key, _title in STAT_LABELS:
            self.stat_values[key].setText(str(getattr(stats, key)))
        self.statusBar().showMessage(
            f"设备在线 · CAN RX {stats.can_rx} · CAN TX {stats.can_tx} · "
            f"总错误/丢弃 {stats.uart_drop + stats.cmd_drop + stats.cmd_bad + stats.can_tx_drop + stats.uart_err}"
        )

    def _request_status(self) -> None:
        if self._worker is not None:
            self._worker.queue_line("V")

    def _request_can_bitrate(self) -> None:
        if self._worker is not None:
            self._worker.queue_line("S?")

    def _apply_can_bitrate(self) -> None:
        if self._worker is None:
            return
        bitrate = self.can_bitrate_combo.currentData()
        if not isinstance(bitrate, int):
            return
        try:
            command = encode_bitrate_command(bitrate, terminator=False)
        except ProtocolError as exc:
            QMessageBox.warning(self, "CAN 波特率错误", str(exc))
            return
        self.can_bitrate_label.setText(f"设备 CAN：正在切换到 {bitrate // 1000} kbit/s…")
        self._worker.queue_line(command)

    def _update_status_polling(self) -> None:
        if self._worker is not None and self.auto_status_checkbox.isChecked():
            self._status_timer.start()
        else:
            self._status_timer.stop()

    def _frame_from_inputs(self) -> CanFrame:
        extended = self.frame_kind_combo.currentText() == "扩展帧"
        remote = self.frame_type_combo.currentText() == "远程帧"
        arbitration_id = parse_identifier(self.id_edit.text(), extended=extended)
        data = b"" if remote else parse_data_bytes(self.data_edit.text())
        return CanFrame(
            arbitration_id=arbitration_id,
            data=data,
            extended=extended,
            remote=remote,
            dlc=self.dlc_spin.value(),
        )

    def _start_send_task(self) -> None:
        if self._worker is None:
            QMessageBox.warning(self, "设备未连接", "请先连接串口设备。")
            return
        try:
            self._frame_from_inputs()
        except ProtocolError as exc:
            QMessageBox.warning(self, "发送参数错误", str(exc))
            return

        self._periodic_timer.stop()
        self._send_task_running = True
        self._send_batches_total = self.send_repeat_spin.value()
        self._send_batches_remaining = self._send_batches_total
        self._send_frames_sent = 0
        self._set_send_task_ui(True)
        self.send_progress_label.setText(
            f"发送任务：0/{self._send_batches_total} 次 · 0 帧"
        )
        self._send_next_batch()

    def _send_next_batch(self) -> None:
        if not self._send_task_running:
            return
        if self._send_batches_remaining <= 0:
            self._finish_send_task(
                f"发送任务：已完成 · {self._send_batches_total} 次 · "
                f"{self._send_frames_sent} 帧"
            )
            return

        for _index in range(self.frames_per_batch_spin.value()):
            frame = self._send_frame(show_errors=False)
            if frame is None:
                error = self._last_send_error or "发送失败。"
                self._finish_send_task(f"发送任务：已停止 · {error}")
                QMessageBox.warning(self, "发送任务已停止", error)
                return
            self._send_frames_sent += 1
            self._advance_send_inputs(frame)

        self._send_batches_remaining -= 1
        completed = self._send_batches_total - self._send_batches_remaining
        self.send_progress_label.setText(
            f"发送任务：{completed}/{self._send_batches_total} 次 · "
            f"{self._send_frames_sent} 帧"
        )
        if self._send_batches_remaining > 0:
            self._periodic_timer.start(self.send_interval_spin.value())
        else:
            self._finish_send_task(
                f"发送任务：已完成 · {self._send_batches_total} 次 · "
                f"{self._send_frames_sent} 帧"
            )

    def _stop_send_task(self, _checked: bool = False) -> None:
        if self._send_task_running:
            completed = self._send_batches_total - self._send_batches_remaining
            self._finish_send_task(
                f"发送任务：已手动停止 · {completed}/{self._send_batches_total} 次 · "
                f"{self._send_frames_sent} 帧"
            )

    def _finish_send_task(self, message: str) -> None:
        self._periodic_timer.stop()
        self._send_task_running = False
        self._send_batches_remaining = 0
        self._set_send_task_ui(False)
        self.send_progress_label.setText(message)

    def _set_send_task_ui(self, running: bool) -> None:
        for widget in (
            self.frame_type_combo,
            self.frame_kind_combo,
            self.dlc_spin,
            self.frames_per_batch_spin,
            self.send_interval_spin,
            self.send_repeat_spin,
            self.id_mode_combo,
            self.id_edit,
        ):
            widget.setEnabled(not running)
        remote = self.frame_type_combo.currentText() == "远程帧"
        self.data_mode_combo.setEnabled(not running and not remote)
        self.data_edit.setEnabled(not running and not remote)
        connected = self._worker is not None
        self.send_button.setEnabled(connected and not running)
        self.stop_send_button.setEnabled(connected and running)

    def _send_frame(self, *, show_errors: bool) -> CanFrame | None:
        self._last_send_error = ""
        if self._worker is None:
            self._last_send_error = "串口未连接。"
            if show_errors:
                QMessageBox.warning(self, "设备未连接", "请先连接串口设备。")
            return None
        try:
            frame = self._frame_from_inputs()
        except ProtocolError as exc:
            self._last_send_error = str(exc)
            if show_errors:
                QMessageBox.warning(self, "发送参数错误", str(exc))
            return None
        command = encode_frame(frame, terminator=False)
        if not self._worker.queue_line(command):
            self._last_send_error = "串口发送队列已满；请增大发送间隔或减少每次帧数。"
            if show_errors:
                QMessageBox.warning(self, "发送过快", self._last_send_error)
            return None
        if not self._capture_paused:
            self._append_frame("TX", frame, command)
        return frame

    def _advance_send_inputs(self, frame: CanFrame) -> None:
        increment_id = self.id_mode_combo.currentText() == "递增"
        increment_data = self.data_mode_combo.currentText() == "递增"
        if not increment_id and not increment_data:
            return

        next_frame = advance_frame(
            frame,
            increment_id=increment_id,
            increment_data=increment_data,
        )
        if increment_id:
            width = 8 if next_frame.extended else 3
            self.id_edit.setText(f"{next_frame.arbitration_id:0{width}X}")
        if increment_data and not next_frame.remote and next_frame.data:
            self.data_edit.setText(next_frame.data_text)

    def _sync_dlc_from_data(self) -> None:
        if self.frame_type_combo.currentText() == "远程帧":
            return
        try:
            data = parse_data_bytes(self.data_edit.text())
        except ProtocolError:
            return
        self.dlc_spin.setValue(len(data))

    def _update_remote_ui(self, frame_type: str) -> None:
        remote = frame_type == "远程帧"
        self.data_edit.setEnabled(not remote and not self._send_task_running)
        self.data_mode_combo.setEnabled(not remote and not self._send_task_running)
        if remote and self.dlc_spin.value() == 0:
            self.dlc_spin.setValue(8)

    def _update_id_hint(self) -> None:
        extended = self.frame_kind_combo.currentText() == "扩展帧"
        self.id_edit.setPlaceholderText("00000000–1FFFFFFF" if extended else "000–7FF")

    def _set_capture_paused(self, paused: bool) -> None:
        self._capture_paused = paused
        self.pause_button.setText("继续显示" if paused else "暂停显示")
        self._show_capture_count()

    def _apply_filters(self) -> None:
        self._proxy_model.set_filters(
            self.id_filter_edit.text(),
            self.direction_filter.currentText(),
            self.type_filter.currentText(),
        )
        self._show_capture_count()

    def _show_capture_count(self) -> None:
        paused = " · 显示已暂停" if self._capture_paused else ""
        self.statusBar().showMessage(
            f"当前显示 {self._proxy_model.rowCount()} / 已记录 {len(self._frame_model.records)} 帧{paused}"
        )

    def _clear_capture(self) -> None:
        self._frame_model.clear()
        self._sequence = 0
        self._show_capture_count()

    def _export_csv(self) -> None:
        if self._proxy_model.rowCount() == 0:
            QMessageBox.information(self, "没有数据", "当前过滤结果中没有可导出的 CAN 报文。")
            return
        default_name = f"can_capture_{datetime.now():%Y%m%d_%H%M%S}.csv"
        path_text, _ = QFileDialog.getSaveFileName(
            self, "导出 CAN 报文", str(Path.home() / default_name), "CSV 文件 (*.csv)"
        )
        if not path_text:
            return
        try:
            with open(path_text, "w", newline="", encoding="utf-8-sig") as output:
                writer = csv.writer(output)
                writer.writerow(("sequence", "timestamp", "direction", "type", "id", "rtr", "dlc", "data", "wire"))
                for proxy_row in range(self._proxy_model.rowCount()):
                    proxy_index = self._proxy_model.index(proxy_row, 0)
                    source_index = self._proxy_model.mapToSource(proxy_index)
                    record = self._frame_model.records[source_index.row()]
                    frame = record.frame
                    writer.writerow(
                        (
                            record.sequence,
                            record.timestamp.isoformat(timespec="milliseconds"),
                            record.direction,
                            "extended" if frame.extended else "standard",
                            frame.id_text,
                            int(frame.remote),
                            frame.dlc,
                            frame.data_text,
                            record.wire_text,
                        )
                    )
        except OSError as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        self.statusBar().showMessage(f"已导出 {self._proxy_model.rowCount()} 帧到 {path_text}")

    def _restore_settings(self) -> None:
        baudrate = self._settings.value("serial/baudrate", 115200, type=int)
        if self.baud_combo.findText(str(baudrate)) >= 0:
            self.baud_combo.setCurrentText(str(baudrate))
        can_bitrate = self._settings.value("can/bitrate", 500_000, type=int)
        can_index = self.can_bitrate_combo.findData(can_bitrate)
        if can_index >= 0:
            self.can_bitrate_combo.setCurrentIndex(can_index)
        geometry = self._settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._settings.setValue("window/geometry", self.saveGeometry())
        if self._send_task_running:
            self._finish_send_task("发送任务：窗口正在关闭")
        if self._worker is not None:
            worker = self._worker
            worker.request_stop()
            if not worker.wait(1500):
                event.ignore()
                QMessageBox.warning(self, "正在关闭串口", "串口线程尚未退出，请稍后再试。")
                return
        event.accept()

    @staticmethod
    def _make_icon() -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#1d4ed8"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(2, 2, 60, 60, 13, 13)
        painter.setPen(QColor("#e0f2fe"))
        font = QFont("Arial", 15, QFont.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "CAN")
        painter.end()
        return QIcon(pixmap)


def configure_application(app: QApplication) -> None:
    app.setApplicationName("UART-CAN 上位机")
    app.setOrganizationName("CANDevice")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    font = QFont("Microsoft YaHei UI", 10)
    app.setFont(font)
