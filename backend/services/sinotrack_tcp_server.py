"""SinoTrack H02 TCP adapter into the canonical GPS-1 writer."""
from __future__ import annotations

import logging
import os
from datetime import datetime
import socketserver

from services.physical_tracker_ingestion import PhysicalTrackerError, PhysicalTrackerIngestor
from services.sinotrack_h02 import H02ProtocolError, HEARTBEAT_TYPES, parse_h02_packet
from services.trip_tracking import TripTrackingError
from services.gps_immobilizer_dispatcher import evaluate_pending_command, mark_command_ready, mark_command_sent, build_s20_command, get_ready_command, ack_latest_sent_command

logger = logging.getLogger("velcore.sinotrack")
MAX_BUFFER_SIZE = 16 * 1024


class SinoTrackRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        buffer = bytearray()
        connection_identifier = None
        zero_speed_streak = 0
        previewed_command_ids = set()
        try:
            while True:
                chunk = self.request.recv(4096)
                if not chunk:
                    return
                buffer.extend(chunk)
                if len(buffer) > MAX_BUFFER_SIZE:
                    raise H02ProtocolError("H02 connection buffer exceeds limit")
                while b"#" in buffer:
                    end = buffer.index(b"#") + 1
                    packet = bytes(buffer[:end]); del buffer[:end]
                    message = parse_h02_packet(packet)
                    logger.info(
                        "SINOTRACK RAW identifier_suffix=%s packet=%s",
                        message.identifier[-4:],
                        packet.decode("ascii", errors="replace"),
                    )
                    if connection_identifier is None:
                        self.server.ingestor.validate_device(message.identifier)
                        connection_identifier = message.identifier
                    elif message.identifier != connection_identifier:
                        raise PhysicalTrackerError("tracker identifier changed on active connection")

                    if message.message_type == "V4" and b",S20," in packet:
                        db = self.server.session_factory()
                        try:
                            ack_result = ack_latest_sent_command(
                                db,
                                message.identifier,
                                max_age_seconds=120,
                            )
                            logger.warning(
                                "IMMOBILIZER ACK RECEIVED device_suffix=%s updated=%s command_id=%s reason=%s raw=%s",
                                message.identifier[-4:],
                                ack_result.get("updated"),
                                ack_result.get("command_id"),
                                ack_result.get("reason"),
                                packet.decode("ascii", errors="replace"),
                            )
                        finally:
                            db.close()

                    if message.point is not None:
                        speed_kmh = float(message.point.get("speed_kmh") or 0.0)

                        if speed_kmh <= 0.0:
                            zero_speed_streak += 1
                        else:
                            zero_speed_streak = 0

                        logger.info(
                            "SinoTrack safety state identifier_suffix=%s speed=%.1f zero_speed_streak=%s",
                            message.identifier[-4:],
                            speed_kmh,
                            zero_speed_streak,
                        )

                        self.server.ingestor.ingest(message.identifier, [message.point])

                        if zero_speed_streak >= 3:
                            db = self.server.session_factory()
                            try:
                                decision = evaluate_pending_command(
                                    db,
                                    message.identifier,
                                    zero_speed_streak=zero_speed_streak,
                                )
                                if decision.get("eligible"):
                                    result = mark_command_ready(
                                        db,
                                        decision.get("command_id"),
                                    )
                                    if result.get("updated"):
                                        logger.warning(
                                            "IMMOBILIZER READY command_id=%s action=%s device_suffix=%s speed=%.1f streak=%s",
                                            result.get("command_id"),
                                            result.get("action"),
                                            message.identifier[-4:],
                                            speed_kmh,
                                            zero_speed_streak,
                                        )

                                    live_send = os.getenv("IMMOBILIZER_LIVE_SEND", "false").strip().lower() == "true"

                                    if live_send:
                                        logger.error(
                                            "IMMOBILIZER LIVE SEND ENABLED but transport execution is not activated yet command_id=%s",
                                            decision.get("command_id"),
                                        )
                                    else:
                                        preview = build_s20_command(
                                            message.identifier,
                                            decision.get("action"),
                                            datetime.utcnow().strftime("%H%M%S"),
                                        ).decode("ascii")
                                        logger.warning(
                                            "IMMOBILIZER WOULD SEND command_id=%s payload=%s",
                                            decision.get("command_id"),
                                            preview,
                                        )
                            finally:
                                db.close()

                        if zero_speed_streak >= 3:
                            db = self.server.session_factory()
                            try:
                                ready = get_ready_command(db, message.identifier)

                                if ready.get("found"):
                                    live_send = (
                                        os.getenv("IMMOBILIZER_LIVE_SEND", "false")
                                        .strip()
                                        .lower()
                                        == "true"
                                    )

                                    if live_send:
                                        command_id = ready.get("command_id")
                                        payload = build_s20_command(
                                            message.identifier,
                                            ready.get("action"),
                                            datetime.utcnow().strftime("%H%M%S"),
                                        )

                                        claimed = mark_command_sent(db, command_id)

                                        if claimed.get("updated"):
                                            try:
                                                self.request.sendall(payload)
                                                logger.warning(
                                                    "IMMOBILIZER SENT command_id=%s action=%s device_suffix=%s payload=%s",
                                                    command_id,
                                                    ready.get("action"),
                                                    message.identifier[-4:],
                                                    payload.decode("ascii"),
                                                )
                                            except Exception as exc:
                                                logger.exception(
                                                    "IMMOBILIZER SEND FAILED command_id=%s error=%s",
                                                    command_id,
                                                    exc,
                                                )
                                        else:
                                            logger.info(
                                                "IMMOBILIZER SEND SKIPPED command_id=%s reason=%s status=%s",
                                                command_id,
                                                claimed.get("reason"),
                                                claimed.get("status"),
                                            )
                                    else:
                                        preview = build_s20_command(
                                            message.identifier,
                                            ready.get("action"),
                                            datetime.utcnow().strftime("%H%M%S"),
                                        ).decode("ascii")

                                        command_id = ready.get("command_id")
                                        if command_id not in previewed_command_ids:
                                            logger.warning(
                                                "IMMOBILIZER WOULD SEND READY command_id=%s payload=%s",
                                                command_id,
                                                preview,
                                            )
                                            previewed_command_ids.add(command_id)
                            finally:
                                db.close()

                    elif message.message_type in HEARTBEAT_TYPES:
                        self.server.ingestor.heartbeat(message.identifier)
                        self.request.sendall(f"*HQ,{message.identifier},{message.message_type}#".encode("ascii"))
                    elif message.message_type in {"V1", "V8"} and message.gps_valid is False:
                        logger.info("Ignored invalid GPS fix identifier_suffix=%s", message.identifier[-4:])
                    else:
                        logger.info("Ignored unsupported H02 status type=%s identifier_suffix=%s",
                                    message.message_type, message.identifier[-4:])
        except (H02ProtocolError, PhysicalTrackerError, TripTrackingError) as exc:
            logger.warning("SinoTrack connection rejected: %s", exc)
        except Exception:
            logger.exception("SinoTrack connection failed")


class SinoTrackTcpServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, session_factory):
        self.session_factory = session_factory
        self.ingestor = PhysicalTrackerIngestor(session_factory)
        super().__init__(address, SinoTrackRequestHandler)


def configured_address() -> tuple[str, int]:
    host = os.getenv("SINOTRACK_HOST", "127.0.0.1").strip()
    raw_port = os.getenv("SINOTRACK_PORT", "8502").strip()
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise RuntimeError("SINOTRACK_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("SINOTRACK_PORT must be between 1 and 65535")
    return host, port
