"""Encoding and decoding for the bridge's SLCAN-like text protocol."""

from __future__ import annotations

from dataclasses import dataclass
import re


MAX_STANDARD_ID = 0x7FF
MAX_EXTENDED_ID = 0x1FFFFFFF
MAX_DATA_LENGTH = 8
CAN_BITRATE_CODE_BY_RATE = {
    10_000: "0",
    20_000: "1",
    50_000: "2",
    100_000: "3",
    125_000: "4",
    250_000: "5",
    500_000: "6",
    800_000: "7",
    1_000_000: "8",
}
CAN_BITRATES = tuple(CAN_BITRATE_CODE_BY_RATE)


class ProtocolError(ValueError):
    """Raised when a command or reply does not match the wire protocol."""


@dataclass(frozen=True, slots=True)
class CanFrame:
    arbitration_id: int
    data: bytes = b""
    extended: bool = False
    remote: bool = False
    dlc: int | None = None

    def __post_init__(self) -> None:
        max_id = MAX_EXTENDED_ID if self.extended else MAX_STANDARD_ID
        if not 0 <= self.arbitration_id <= max_id:
            frame_name = "扩展帧" if self.extended else "标准帧"
            raise ProtocolError(f"{frame_name} ID 必须在 0x0 到 0x{max_id:X} 之间")

        actual_dlc = len(self.data) if self.dlc is None else self.dlc
        if not 0 <= actual_dlc <= MAX_DATA_LENGTH:
            raise ProtocolError("DLC 必须在 0 到 8 之间")
        if self.remote:
            if self.data:
                raise ProtocolError("远程帧不能携带数据")
        elif len(self.data) != actual_dlc:
            raise ProtocolError(f"DLC={actual_dlc}，但输入了 {len(self.data)} 个数据字节")

        object.__setattr__(self, "dlc", actual_dlc)

    @property
    def id_text(self) -> str:
        width = 8 if self.extended else 3
        return f"{self.arbitration_id:0{width}X}"

    @property
    def data_text(self) -> str:
        return " ".join(f"{byte:02X}" for byte in self.data)

    @property
    def frame_type_text(self) -> str:
        base = "扩展" if self.extended else "标准"
        return f"{base}远程帧" if self.remote else f"{base}数据帧"


@dataclass(frozen=True, slots=True)
class DeviceStats:
    can_rx: int
    can_tx: int
    uart_drop: int
    cmd_drop: int
    cmd_bad: int
    can_tx_drop: int
    uart_err: int
    can_recover: int


@dataclass(frozen=True, slots=True)
class CanBitrateStatus:
    bitrate: int


@dataclass(frozen=True, slots=True)
class DeviceError:
    command: str


_STATS_FIELDS = (
    "can_rx",
    "can_tx",
    "uart_drop",
    "cmd_drop",
    "cmd_bad",
    "can_tx_drop",
    "uart_err",
    "can_recover",
)


def parse_identifier(text: str, *, extended: bool) -> int:
    value_text = text.strip()
    if value_text.lower().startswith("0x"):
        value_text = value_text[2:]
    if not value_text or not re.fullmatch(r"[0-9a-fA-F]+", value_text):
        raise ProtocolError("CAN ID 必须是十六进制数")
    value = int(value_text, 16)
    max_id = MAX_EXTENDED_ID if extended else MAX_STANDARD_ID
    if value > max_id:
        raise ProtocolError(f"CAN ID 超出范围，最大值为 0x{max_id:X}")
    return value


def parse_data_bytes(text: str) -> bytes:
    """Accept either compact hex or bytes separated by spaces/commas/dashes."""
    compact = re.sub(r"[\s,;:_-]+", "", text.strip())
    if compact.lower().startswith("0x"):
        compact = compact[2:]
    if not compact:
        return b""
    if not re.fullmatch(r"[0-9a-fA-F]+", compact):
        raise ProtocolError("数据只能包含十六进制字节")
    if len(compact) % 2:
        raise ProtocolError("每个数据字节必须包含两位十六进制数")
    data = bytes.fromhex(compact)
    if len(data) > MAX_DATA_LENGTH:
        raise ProtocolError("经典 CAN 一帧最多包含 8 个数据字节")
    return data


def encode_frame(frame: CanFrame, *, terminator: bool = True) -> str:
    if frame.extended:
        kind = "R" if frame.remote else "T"
        id_text = f"{frame.arbitration_id:08X}"
    else:
        kind = "r" if frame.remote else "t"
        id_text = f"{frame.arbitration_id:03X}"
    payload = "" if frame.remote else frame.data.hex().upper()
    command = f"{kind}{id_text}{frame.dlc}{payload}"
    return command + ("\r" if terminator else "")


def encode_bitrate_command(bitrate: int, *, terminator: bool = True) -> str:
    try:
        code = CAN_BITRATE_CODE_BY_RATE[bitrate]
    except KeyError as exc:
        choices = ", ".join(f"{rate // 1000} kbit/s" for rate in CAN_BITRATES)
        raise ProtocolError(f"不支持的 CAN 波特率；可选值：{choices}") from exc
    return f"S{code}" + ("\r" if terminator else "")


def advance_frame(
    frame: CanFrame,
    *,
    increment_id: bool = False,
    increment_data: bool = False,
) -> CanFrame:
    """Return the next periodic frame, wrapping ID and payload at their width."""
    max_id = MAX_EXTENDED_ID if frame.extended else MAX_STANDARD_ID
    arbitration_id = (
        (frame.arbitration_id + 1) % (max_id + 1)
        if increment_id
        else frame.arbitration_id
    )

    data = frame.data
    if increment_data and data and not frame.remote:
        modulus = 1 << (len(data) * 8)
        next_value = (int.from_bytes(data, byteorder="big") + 1) % modulus
        data = next_value.to_bytes(len(data), byteorder="big")

    return CanFrame(
        arbitration_id=arbitration_id,
        data=data,
        extended=frame.extended,
        remote=frame.remote,
        dlc=frame.dlc,
    )


def decode_frame(line: str) -> CanFrame:
    text = line.rstrip("\r\n")
    if not text or text[0] not in "tTrR":
        raise ProtocolError("不是 CAN 帧")

    kind = text[0]
    extended = kind in "TR"
    remote = kind in "rR"
    id_width = 8 if extended else 3
    header_length = 1 + id_width + 1
    if len(text) < header_length:
        raise ProtocolError("CAN 帧头长度不足")

    id_text = text[1 : 1 + id_width]
    if not re.fullmatch(r"[0-9a-fA-F]+", id_text):
        raise ProtocolError("CAN ID 包含非法字符")
    arbitration_id = int(id_text, 16)
    max_id = MAX_EXTENDED_ID if extended else MAX_STANDARD_ID
    if arbitration_id > max_id:
        raise ProtocolError(f"CAN ID 超出范围，最大值为 0x{max_id:X}")

    dlc_text = text[1 + id_width]
    if dlc_text not in "012345678":
        raise ProtocolError("DLC 必须是 0 到 8")
    dlc = int(dlc_text)
    payload_text = text[header_length:]

    if remote:
        if payload_text:
            raise ProtocolError("远程帧不能携带数据")
        data = b""
    else:
        if len(payload_text) != dlc * 2:
            raise ProtocolError("数据长度与 DLC 不一致")
        if payload_text and not re.fullmatch(r"[0-9a-fA-F]+", payload_text):
            raise ProtocolError("数据包含非法十六进制字符")
        data = bytes.fromhex(payload_text)

    return CanFrame(
        arbitration_id=arbitration_id,
        data=data,
        extended=extended,
        remote=remote,
        dlc=dlc,
    )


def decode_stats(line: str) -> DeviceStats:
    parts = line.rstrip("\r\n").split()
    if len(parts) != 9 or parts[0] != "V":
        raise ProtocolError("状态回复格式不正确")
    try:
        values = [int(value, 10) for value in parts[1:]]
    except ValueError as exc:
        raise ProtocolError("状态计数器必须是十进制整数") from exc
    if any(value < 0 for value in values):
        raise ProtocolError("状态计数器不能为负数")
    return DeviceStats(**dict(zip(_STATS_FIELDS, values, strict=True)))


def decode_bitrate_status(line: str) -> CanBitrateStatus:
    parts = line.rstrip("\r\n").split()
    if len(parts) != 2 or parts[0] != "S":
        raise ProtocolError("CAN 波特率回复格式不正确")
    try:
        bitrate = int(parts[1], 10)
    except ValueError as exc:
        raise ProtocolError("CAN 波特率必须是十进制整数") from exc
    if bitrate not in CAN_BITRATE_CODE_BY_RATE:
        raise ProtocolError("设备返回了不支持的 CAN 波特率")
    return CanBitrateStatus(bitrate)


def decode_device_error(line: str) -> DeviceError:
    parts = line.rstrip("\r\n").split()
    if len(parts) != 2 or parts[0] != "E" or not parts[1]:
        raise ProtocolError("设备错误回复格式不正确")
    return DeviceError(parts[1])


def decode_device_line(line: str) -> CanFrame | DeviceStats | CanBitrateStatus | DeviceError:
    text = line.rstrip("\r\n")
    if text.startswith("V "):
        return decode_stats(text)
    if text.startswith("S "):
        return decode_bitrate_status(text)
    if text.startswith("E "):
        return decode_device_error(text)
    return decode_frame(text)
