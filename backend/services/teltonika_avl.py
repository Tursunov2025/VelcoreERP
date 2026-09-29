"""Strict Teltonika Codec 8/8E parsing and canonical point mapping."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone


class TeltonikaProtocolError(ValueError):
    """Raised when an AVL frame is malformed or fails integrity checks."""


@dataclass(frozen=True)
class AvlRecord:
    timestamp_ms: int
    priority: int
    longitude: float
    latitude: float
    altitude_m: int
    heading_deg: int
    satellites: int
    speed_kmh: int
    event_id: int
    raw: bytes
    index: int


class _Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def take(self, size: int) -> bytes:
        end = self.pos + size
        if size < 0 or end > len(self.data):
            raise TeltonikaProtocolError("truncated AVL record")
        out = self.data[self.pos:end]
        self.pos = end
        return out

    def uint(self, size: int) -> int:
        return int.from_bytes(self.take(size), "big", signed=False)

    def sint(self, size: int) -> int:
        return int.from_bytes(self.take(size), "big", signed=True)


def crc16_ibm(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def _skip_codec8_io(reader: _Reader) -> int:
    event_id = reader.uint(1)
    declared_total = reader.uint(1)
    actual_total = 0
    for value_size in (1, 2, 4, 8):
        count = reader.uint(1)
        actual_total += count
        reader.take(count * (1 + value_size))
    if actual_total != declared_total:
        raise TeltonikaProtocolError("Codec 8 IO element count mismatch")
    return event_id


def _skip_codec8e_io(reader: _Reader) -> int:
    event_id = reader.uint(2)
    reader.uint(1)  # generation type
    declared_total = reader.uint(2)
    actual_total = 0
    for value_size in (1, 2, 4, 8):
        count = reader.uint(2)
        actual_total += count
        reader.take(count * (2 + value_size))
    variable_count = reader.uint(2)
    actual_total += variable_count
    for _ in range(variable_count):
        reader.uint(2)
        reader.take(reader.uint(2))
    if actual_total != declared_total:
        raise TeltonikaProtocolError("Codec 8 Extended IO element count mismatch")
    return event_id


def parse_avl_frame(frame: bytes) -> tuple[int, list[AvlRecord]]:
    """Parse one complete Teltonika TCP AVL frame including preamble and CRC."""
    if len(frame) < 12:
        raise TeltonikaProtocolError("AVL frame is too short")
    if frame[:4] != b"\x00\x00\x00\x00":
        raise TeltonikaProtocolError("invalid AVL preamble")
    data_length = int.from_bytes(frame[4:8], "big")
    if data_length <= 0 or len(frame) != 8 + data_length + 4:
        raise TeltonikaProtocolError("AVL packet length mismatch")
    data = frame[8:8 + data_length]
    supplied_crc = int.from_bytes(frame[-4:], "big")
    if supplied_crc > 0xFFFF or crc16_ibm(data) != supplied_crc:
        raise TeltonikaProtocolError("AVL CRC mismatch")

    reader = _Reader(data)
    codec = reader.uint(1)
    if codec not in (0x08, 0x8E):
        raise TeltonikaProtocolError(f"unsupported codec 0x{codec:02X}")
    count = reader.uint(1)
    if count == 0:
        raise TeltonikaProtocolError("empty AVL packet")

    records: list[AvlRecord] = []
    for index in range(count):
        start = reader.pos
        timestamp_ms = reader.uint(8)
        priority = reader.uint(1)
        longitude = reader.sint(4) / 10_000_000
        latitude = reader.sint(4) / 10_000_000
        altitude = reader.uint(2)
        heading = reader.uint(2)
        satellites = reader.uint(1)
        speed = reader.uint(2)
        event_id = _skip_codec8_io(reader) if codec == 0x08 else _skip_codec8e_io(reader)
        raw = data[start:reader.pos]
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise TeltonikaProtocolError("AVL coordinates are outside valid bounds")
        if heading > 360:
            raise TeltonikaProtocolError("AVL heading is outside valid bounds")
        records.append(AvlRecord(timestamp_ms, priority, longitude, latitude, altitude,
                                 heading, satellites, speed, event_id, raw, index))

    repeated_count = reader.uint(1)
    if repeated_count != count:
        raise TeltonikaProtocolError("AVL record counts do not match")
    if reader.pos != len(data):
        raise TeltonikaProtocolError("unexpected bytes after AVL records")
    return codec, records


def canonical_points(imei: str, records: list[AvlRecord]) -> list[dict]:
    points = []
    for record in records:
        identity = b"\x00".join((imei.encode("ascii"), str(record.timestamp_ms).encode("ascii"),
                                  str(record.index).encode("ascii"), record.raw))
        points.append({
            "client_point_id": f"teltonika:{hashlib.sha256(identity).hexdigest()}",
            "latitude": record.latitude,
            "longitude": record.longitude,
            "accuracy_m": None,
            "speed_kmh": float(record.speed_kmh),
            "heading_deg": float(record.heading_deg),
            "battery_level": None,
            "captured_at": datetime.fromtimestamp(record.timestamp_ms / 1000, tz=timezone.utc),
            "was_queued": True,
        })
    return points
