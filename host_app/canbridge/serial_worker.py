"""Background serial I/O worker."""

from __future__ import annotations

import errno
from queue import Empty, Full, Queue
import sys
from threading import Event

import serial
from PySide6.QtCore import QThread, Signal


class SerialWorker(QThread):
    line_received = Signal(str)
    port_opened = Signal(str)
    port_closed = Signal()
    io_error = Signal(str)

    TX_QUEUE_MAX_LINES = 2048
    TX_DRAIN_BATCH_LINES = 32

    def __init__(self, port: str, baudrate: int, parent=None) -> None:
        super().__init__(parent)
        self._port = port
        self._baudrate = baudrate
        self._stop_event = Event()
        self._tx_queue: Queue[bytes] = Queue(maxsize=self.TX_QUEUE_MAX_LINES)

    def queue_line(self, text: str) -> bool:
        wire = text.rstrip("\r\n").encode("ascii") + b"\r"
        try:
            self._tx_queue.put_nowait(wire)
        except Full:
            return False
        return True

    def request_stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        connection: serial.Serial | None = None
        receive_buffer = bytearray()
        try:
            connection = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.05,
                write_timeout=0.5,
            )
            connection.reset_input_buffer()
            self.port_opened.emit(self._port)

            while not self._stop_event.is_set():
                self._drain_transmit_queue(connection)
                incoming = connection.read(max(connection.in_waiting, 1))
                if incoming:
                    self._consume_bytes(receive_buffer, incoming)
        except (serial.SerialException, OSError) as exc:
            if not self._stop_event.is_set():
                message = str(exc)
                if sys.platform.startswith("linux") and exc.errno == errno.EACCES:
                    message = (
                        f"没有访问串口 {self._port} 的权限。请将当前用户加入设备所属用户组"
                        "（如 dialout 或 uucp）并重新登录，详见上位机 README。\n"
                        f"原始错误：{exc}"
                    )
                self.io_error.emit(message)
        finally:
            if connection is not None and connection.is_open:
                try:
                    connection.close()
                except (serial.SerialException, OSError):
                    pass
            self.port_closed.emit()

    def _drain_transmit_queue(self, connection: serial.Serial) -> None:
        # Bound each drain pass so sustained periodic traffic cannot starve
        # serial receive handling or make a stop request wait indefinitely.
        for _ in range(self.TX_DRAIN_BATCH_LINES):
            try:
                payload = self._tx_queue.get_nowait()
            except Empty:
                return
            connection.write(payload)

    def _consume_bytes(self, buffer: bytearray, incoming: bytes) -> None:
        for byte in incoming:
            if byte in (10, 13):
                if buffer:
                    self.line_received.emit(buffer.decode("ascii", errors="replace"))
                    buffer.clear()
            elif len(buffer) < 512:
                buffer.append(byte)
            else:
                buffer.clear()
                self.io_error.emit("收到超过 512 字节且未结束的数据行，已丢弃")
