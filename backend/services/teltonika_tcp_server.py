"""Teltonika TCP transport adapter for the canonical GPS-1 writer."""
from __future__ import annotations

import logging
import os
import socketserver

from services.physical_tracker_ingestion import PhysicalTrackerError, PhysicalTrackerIngestor
from services.teltonika_avl import TeltonikaProtocolError, canonical_points, parse_avl_frame
from services.trip_tracking import TripTrackingError

logger = logging.getLogger("velcore.teltonika")
MAX_AVL_DATA_LENGTH = 128 * 1024


def validate_imei(raw: bytes) -> str:
    try:
        imei = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise TeltonikaProtocolError("IMEI is not ASCII") from exc
    if len(imei) != 15 or not imei.isdigit():
        raise TeltonikaProtocolError("IMEI must contain exactly 15 digits")
    return imei


class TeltonikaIngestor:
    def __init__(self, session_factory):
        self.canonical = PhysicalTrackerIngestor(session_factory)

    def validate_device(self, imei: str) -> None:
        self.canonical.validate_device(imei)

    def ingest(self, imei: str, frame: bytes) -> int:
        _codec, records = parse_avl_frame(frame)
        self.canonical.ingest(imei, canonical_points(imei, records))
        return len(records)  # handler ACK follows only after canonical commit


def _read_exact(sock, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise EOFError("tracker disconnected during framed read")
        chunks.extend(chunk)
    return bytes(chunks)


class TeltonikaRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            imei_length = int.from_bytes(_read_exact(self.request, 2), "big")
            if imei_length != 15:
                raise TeltonikaProtocolError("IMEI length prefix must be 15")
            imei = validate_imei(_read_exact(self.request, imei_length))
            try:
                self.server.ingestor.validate_device(imei)
            except PhysicalTrackerError as exc:
                logger.warning("Teltonika handshake rejected: %s", exc)
                self.request.sendall(b"\x00")
                return
            self.request.sendall(b"\x01")

            while True:
                header = _read_exact(self.request, 8)
                if header[:4] != b"\x00\x00\x00\x00":
                    raise TeltonikaProtocolError("invalid AVL preamble")
                data_length = int.from_bytes(header[4:], "big")
                if data_length <= 0 or data_length > MAX_AVL_DATA_LENGTH:
                    raise TeltonikaProtocolError("invalid AVL data length")
                frame = header + _read_exact(self.request, data_length + 4)
                accepted = self.server.ingestor.ingest(imei, frame)
                self.request.sendall(accepted.to_bytes(4, "big"))
        except EOFError:
            return
        except (TeltonikaProtocolError, PhysicalTrackerError, TripTrackingError) as exc:
            logger.warning("Teltonika connection rejected: %s", exc)
        except Exception:
            logger.exception("Teltonika connection failed")


class TeltonikaTcpServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, session_factory):
        self.ingestor = TeltonikaIngestor(session_factory)
        super().__init__(address, TeltonikaRequestHandler)


def configured_address() -> tuple[str, int]:
    host = os.getenv("TELTONIKA_HOST", "127.0.0.1").strip()
    raw_port = os.getenv("TELTONIKA_PORT", "8501").strip()
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise RuntimeError("TELTONIKA_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("TELTONIKA_PORT must be between 1 and 65535")
    return host, port
