"""Defensive parser for SinoTrack/Cantrack H02 ASCII messages."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone


class H02ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class H02Message:
    identifier: str
    message_type: str
    raw: bytes
    point: dict | None = None
    gps_valid: bool | None = None


_IDENTIFIER = re.compile(r"^[0-9]{1,180}$")
HEARTBEAT_TYPES = frozenset({"V0", "HTBT", "XT"})


def _coordinate(value: str, hemisphere: str, degree_digits: int) -> float:
    if hemisphere not in ({"N", "S"} if degree_digits == 2 else {"E", "W"}):
        raise H02ProtocolError("invalid coordinate hemisphere")
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
        raise H02ProtocolError("invalid coordinate number")
    whole, dot, fraction = value.partition(".")
    if len(whole) != degree_digits + 2:
        raise H02ProtocolError("invalid degree/minute coordinate width")
    degrees = int(whole[:degree_digits])
    minutes = float(whole[degree_digits:] + (dot + fraction if dot else ""))
    if not 0 <= minutes < 60:
        raise H02ProtocolError("coordinate minutes outside range")
    result = degrees + minutes / 60
    limit = 90 if degree_digits == 2 else 180
    if result > limit:
        raise H02ProtocolError("coordinate outside geographic range")
    if hemisphere in {"S", "W"}:
        result = -result
    return result


def _utc_datetime(date_value: str, time_value: str) -> datetime:
    if not re.fullmatch(r"[0-9]{6}", date_value) or not re.fullmatch(r"[0-9]{6}", time_value):
        raise H02ProtocolError("H02 date/time must use DDMMYY and HHMMSS")
    try:
        parsed = datetime.strptime(date_value + time_value, "%d%m%y%H%M%S")
    except ValueError as exc:
        raise H02ProtocolError("invalid H02 UTC date/time") from exc
    return parsed.replace(tzinfo=timezone.utc)


def parse_h02_packet(packet: bytes) -> H02Message:
    if len(packet) > 4096:
        raise H02ProtocolError("H02 packet exceeds size limit")
    try:
        text = packet.decode("ascii")
    except UnicodeDecodeError as exc:
        raise H02ProtocolError("H02 packet is not ASCII") from exc
    if not text.startswith("*HQ,") or not text.endswith("#"):
        raise H02ProtocolError("invalid H02 envelope")
    fields = text[4:-1].split(",")
    if len(fields) < 2:
        raise H02ProtocolError("H02 packet has no identifier/type")
    identifier, message_type = fields[0], fields[1].upper()
    if not _IDENTIFIER.fullmatch(identifier):
        raise H02ProtocolError("invalid H02 tracker identifier")
    if message_type in HEARTBEAT_TYPES:
        return H02Message(identifier, message_type, packet)
    if message_type not in {"V1", "V8"}:
        return H02Message(identifier, message_type, packet)
    if len(fields) < 12:
        raise H02ProtocolError("V1 packet is missing required fields")

    gps_flag = fields[3].upper()
    if gps_flag not in {"A", "V"}:
        raise H02ProtocolError("invalid GPS validity flag")
    if gps_flag == "V":
        return H02Message(identifier, message_type, packet, gps_valid=False)

    latitude = _coordinate(fields[4], fields[5].upper(), 2)
    longitude = _coordinate(fields[6], fields[7].upper(), 3)
    try:
        speed_knots = float(fields[8])
        heading = float(fields[9])
    except ValueError as exc:
        raise H02ProtocolError("invalid H02 speed/course") from exc
    if not 0 <= speed_knots <= 1000 or not 0 <= heading < 360:
        raise H02ProtocolError("H02 speed/course outside range")
    captured_at = _utc_datetime(fields[10], fields[2])
    raw_hash = hashlib.sha256(packet).hexdigest()
    identity = "\x00".join((identifier, captured_at.isoformat(), format(latitude, ".8f"),
                             format(longitude, ".8f"), raw_hash))
    point = {
        "client_point_id": f"sinotrack:{hashlib.sha256(identity.encode('ascii')).hexdigest()}",
        "latitude": latitude,
        "longitude": longitude,
        "accuracy_m": None,
        "speed_kmh": speed_knots * 1.852,
        "heading_deg": heading,
        "battery_level": None,
        "captured_at": captured_at,
        "was_queued": True,
    }
    return H02Message(identifier, message_type, packet, point=point, gps_valid=True)
