from __future__ import annotations

import errno
import os
import select
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import serial
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from canbridge.serial_worker import SerialWorker


class FakeConnection:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, payload: bytes) -> None:
        self.writes.append(payload)


class SerialWorkerQueueTests(unittest.TestCase):
    def test_queue_has_backpressure(self) -> None:
        worker = SerialWorker("COM0", 115200)
        for index in range(worker.TX_QUEUE_MAX_LINES):
            self.assertTrue(worker.queue_line(f"V{index}"))
        self.assertFalse(worker.queue_line("overflow"))

    def test_drain_is_bounded_to_keep_receive_responsive(self) -> None:
        worker = SerialWorker("COM0", 115200)
        connection = FakeConnection()
        for index in range(worker.TX_DRAIN_BATCH_LINES + 5):
            self.assertTrue(worker.queue_line(f"V{index}"))

        worker._drain_transmit_queue(connection)  # noqa: SLF001

        self.assertEqual(len(connection.writes), worker.TX_DRAIN_BATCH_LINES)
        self.assertTrue(all(payload.endswith(b"\r") for payload in connection.writes))


class SerialWorkerLinuxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux serial device test")
    def test_permission_error_explains_device_group_access(self) -> None:
        worker = SerialWorker("/dev/ttyUSB0", 115200)
        errors = QSignalSpy(worker.io_error)
        closed = QSignalSpy(worker.port_closed)
        with patch("canbridge.serial_worker.serial.Serial", side_effect=serial.SerialException(errno.EACCES, "Permission denied")):
            worker.run()
        self.assertEqual(errors.count(), 1)
        self.assertIn("dialout", errors.at(0)[0])
        self.assertIn("/dev/ttyUSB0", errors.at(0)[0])
        self.assertEqual(closed.count(), 1)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Requires a Linux pseudo-terminal")
    def test_real_serial_thread_reads_and_writes_linux_device(self) -> None:
        master, slave = os.openpty()
        worker = SerialWorker(os.ttyname(slave), 115200)
        opened = QSignalSpy(worker.port_opened)
        received = QSignalSpy(worker.line_received)
        closed = QSignalSpy(worker.port_closed)
        errors = QSignalSpy(worker.io_error)
        try:
            worker.start()
            for _ in range(100):
                self.app.processEvents()
                if opened.count():
                    break
                QTest.qWait(10)
            self.assertEqual(opened.count(), 1)
            self.assertTrue(worker.queue_line("t12321122"))
            readable, _, _ = select.select([master], [], [], 2)
            self.assertTrue(readable, "Serial command was not written to the pseudo-terminal")
            self.assertEqual(os.read(master, 1024), b"t12321122\r")
            os.write(master, b"t3212DEAD\r\nV 1 2 0 0 0 0 0 0\r")
            for _ in range(100):
                self.app.processEvents()
                if received.count() == 2:
                    break
                QTest.qWait(10)
            self.assertEqual(received.count(), 2)
            self.assertEqual(received.at(0)[0], "t3212DEAD")
            self.assertEqual(received.at(1)[0], "V 1 2 0 0 0 0 0 0")
            self.assertEqual(errors.count(), 0)
        finally:
            worker.request_stop()
            stopped = worker.wait(2000)
            self.app.processEvents()
            os.close(master)
            os.close(slave)
        self.assertTrue(stopped)
        self.assertEqual(closed.count(), 1)


if __name__ == "__main__":
    unittest.main()
