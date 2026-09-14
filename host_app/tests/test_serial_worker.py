from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
