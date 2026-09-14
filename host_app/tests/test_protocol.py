from __future__ import annotations

import unittest

from canbridge.protocol import (
    CAN_BITRATES,
    CanBitrateStatus,
    CanFrame,
    DeviceError,
    DeviceStats,
    ProtocolError,
    advance_frame,
    decode_bitrate_status,
    decode_device_line,
    decode_frame,
    decode_stats,
    encode_bitrate_command,
    encode_frame,
    parse_data_bytes,
    parse_identifier,
)


class ProtocolTests(unittest.TestCase):
    def test_standard_frame_round_trip(self) -> None:
        frame = CanFrame(0x123, bytes.fromhex("1122334455667788"))
        wire = encode_frame(frame)
        self.assertEqual(wire, "t12381122334455667788\r")
        self.assertEqual(decode_frame(wire), frame)

    def test_extended_frame_round_trip(self) -> None:
        frame = CanFrame(0x1ABCDE, bytes.fromhex("DEADBE"), extended=True)
        self.assertEqual(decode_frame(encode_frame(frame)), frame)

    def test_remote_frame_has_dlc_but_no_payload(self) -> None:
        frame = decode_frame("r4568")
        self.assertTrue(frame.remote)
        self.assertEqual(frame.dlc, 8)
        self.assertEqual(frame.data, b"")
        self.assertEqual(encode_frame(frame), "r4568\r")

    def test_data_input_accepts_compact_and_separated_hex(self) -> None:
        expected = bytes.fromhex("11223344")
        self.assertEqual(parse_data_bytes("11223344"), expected)
        self.assertEqual(parse_data_bytes("11 22,33-44"), expected)

    def test_identifier_accepts_optional_prefix(self) -> None:
        self.assertEqual(parse_identifier("0x7ff", extended=False), 0x7FF)
        self.assertEqual(parse_identifier("1FFFFFFF", extended=True), 0x1FFFFFFF)

    def test_status_reply(self) -> None:
        stats = decode_stats("V 1 2 3 4 5 6 7 8\r")
        self.assertEqual(stats, DeviceStats(1, 2, 3, 4, 5, 6, 7, 8))
        self.assertIsInstance(decode_device_line("V 1 2 3 4 5 6 7 8"), DeviceStats)

    def test_bitrate_commands_and_reply(self) -> None:
        expected = (10_000, 20_000, 50_000, 100_000, 125_000, 250_000, 500_000, 800_000, 1_000_000)
        self.assertEqual(CAN_BITRATES, expected)
        for code, bitrate in enumerate(expected):
            self.assertEqual(encode_bitrate_command(bitrate), f"S{code}\r")
        self.assertEqual(decode_bitrate_status("S 500000\r"), CanBitrateStatus(500_000))
        self.assertIsInstance(decode_device_line("S 125000"), CanBitrateStatus)

    def test_device_error_reply(self) -> None:
        self.assertEqual(decode_device_line("E S\r"), DeviceError("S"))

    def test_periodic_frame_increment(self) -> None:
        frame = CanFrame(0x7FF, bytes.fromhex("00FF"))
        advanced = advance_frame(frame, increment_id=True, increment_data=True)
        self.assertEqual(advanced.arbitration_id, 0)
        self.assertEqual(advanced.data, bytes.fromhex("0100"))

        wrapped = advance_frame(
            CanFrame(0x1FFFFFFF, bytes.fromhex("FFFF"), extended=True),
            increment_id=True,
            increment_data=True,
        )
        self.assertEqual(wrapped.arbitration_id, 0)
        self.assertEqual(wrapped.data, bytes.fromhex("0000"))

    def test_remote_frame_has_no_incrementing_payload(self) -> None:
        frame = CanFrame(0x123, remote=True, dlc=8)
        self.assertEqual(
            advance_frame(frame, increment_data=True),
            frame,
        )

    def test_rejects_unsupported_bitrate(self) -> None:
        with self.assertRaises(ProtocolError):
            encode_bitrate_command(83_333)
        with self.assertRaises(ProtocolError):
            decode_bitrate_status("S 83333")

    def test_rejects_out_of_range_id(self) -> None:
        with self.assertRaises(ProtocolError):
            decode_frame("t8000")

    def test_rejects_bad_dlc(self) -> None:
        with self.assertRaises(ProtocolError):
            decode_frame("t1239")

    def test_rejects_payload_length_mismatch(self) -> None:
        with self.assertRaises(ProtocolError):
            decode_frame("t123211")
        with self.assertRaises(ProtocolError):
            CanFrame(0x123, b"\x11", dlc=2)

    def test_rejects_more_than_eight_data_bytes(self) -> None:
        with self.assertRaises(ProtocolError):
            parse_data_bytes("00 11 22 33 44 55 66 77 88")


if __name__ == "__main__":
    unittest.main()
