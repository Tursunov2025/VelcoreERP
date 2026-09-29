"""Disposable parser, canonical-writer, and real TCP framing tests."""
from __future__ import annotations

import os
import shutil
import socket
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
ROOT = Path(tempfile.mkdtemp(prefix="velcore-teltonika-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB.replace(chr(92), '/')}", "DB_PATH": DB,
    "DATA_ROOT": str(ROOT), "DATABASE_GUARD": "false", "ENVIRONMENT": "test",
    "JWT_SECRET_KEY": "teltonika-test-secret",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from models import (MesGpsDevice, MesTrip, MesTripLatestLocation, MesTripLocation,
                    MesTripTrackingSession, MesVehicle, ProductionProject,
                    ProjectReleaseSnapshot, User)  # noqa: E402
from services.teltonika_avl import crc16_ibm, parse_avl_frame  # noqa: E402
from services.teltonika_tcp_server import TeltonikaTcpServer  # noqa: E402

IMEI = "356307042441013"


def setup_module():
    Base.metadata.create_all(engine)
    run_migrations(); run_migrations()


def teardown_module():
    engine.dispose()
    Path(DB).unlink(missing_ok=True)
    shutil.rmtree(ROOT, ignore_errors=True)


def _seed(*, status="active", trip_status="dispatched", imei=IMEI):
    db = SessionLocal(); suffix = uuid4().hex[:8]
    driver = User(username=f"tel-driver-{suffix}", role="driver", department="Logistika")
    project = ProductionProject(project_code=f"TEL-{suffix}", project_name="Teltonika test",
                                customer_name_snapshot="TEST", destination_city="Toshkent",
                                site_name="Atlas", full_address="TEST Atlas", status="shipped",
                                release_revision=1, created_by="test")
    vehicle = MesVehicle(vehicle_type="truck", registration_number=f"TEL{suffix}",
                         max_payload_kg=1000, internal_length_mm=4000,
                         internal_width_mm=2000, internal_height_mm=2000,
                         created_by="test", updated_by="test")
    db.add_all([driver, project, vehicle]); db.flush()
    release = ProjectReleaseSnapshot(project_id=project.id, revision=1, source_project_version=1,
                                     idempotency_key=f"release-{suffix}", checksum="0" * 64,
                                     released_by="test")
    db.add(release); db.flush()
    departure = datetime.utcnow() - timedelta(minutes=2)
    trip = MesTrip(trip_number=f"TEL-TRIP-{suffix}", vehicle_id=vehicle.id,
                   driver_user_id=driver.id, project_id=project.id, release_id=release.id,
                   destination_city="Toshkent", destination_site="Atlas",
                   destination_address="TEST Atlas", status=trip_status,
                   actual_departure_at=departure, created_by="test", updated_by="test")
    db.add(trip); db.flush()
    device = MesGpsDevice(device_identifier=imei, vehicle_id=vehicle.id,
                          driver_user_id=driver.id, status=status,
                          created_by="test", updated_by="test")
    db.add(device); db.flush()
    session = MesTripTrackingSession(trip_id=trip.id, vehicle_id=vehicle.id,
                                     driver_user_id=driver.id, device_id=device.id,
                                     client_session_id=f"tel-session-{suffix}", status="active",
                                     authorization_hash="adapter-does-not-use-this-token",
                                     authorization_expires_at=datetime.utcnow() + timedelta(hours=1))
    db.add(session); db.commit()
    ids = device.id, session.id, trip.id
    db.close(); return ids


def _record(codec: int, captured: datetime, lat=41.311081, lon=69.240562,
            speed=25, heading=90, event_id=0):
    timestamp = int(captured.timestamp() * 1000)
    gps = (timestamp.to_bytes(8, "big") + b"\x00" +
           int(lon * 10_000_000).to_bytes(4, "big", signed=True) +
           int(lat * 10_000_000).to_bytes(4, "big", signed=True) +
           (450).to_bytes(2, "big") + heading.to_bytes(2, "big") + b"\x0a" +
           speed.to_bytes(2, "big"))
    if codec == 0x08:
        return gps + event_id.to_bytes(1, "big") + b"\x00\x00\x00\x00\x00"
    return gps + event_id.to_bytes(2, "big") + b"\x00" + (0).to_bytes(2, "big") + (b"\x00\x00" * 5)


def _frame(codec: int, records: list[bytes]):
    data = bytes([codec, len(records)]) + b"".join(records) + bytes([len(records)])
    return b"\x00\x00\x00\x00" + len(data).to_bytes(4, "big") + data + crc16_ibm(data).to_bytes(4, "big")


def _connect(port=8501, imei=IMEI):
    sock = socket.create_connection(("127.0.0.1", port), timeout=2)
    handshake = len(imei).to_bytes(2, "big") + imei.encode("ascii")
    for byte in handshake:  # force partial TCP reads
        sock.sendall(bytes([byte]))
    return sock


class _Server:
    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def __enter__(self):
        self.server = TeltonikaTcpServer(("127.0.0.1", 8501), self.session_factory)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start(); return self.server

    def __exit__(self, *_args):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)


def test_codec8_and_codec8e_parsers_and_crc():
    now = datetime.now(timezone.utc)
    for codec in (0x08, 0x8E):
        frame = _frame(codec, [_record(codec, now)])
        parsed_codec, records = parse_avl_frame(frame)
        assert parsed_codec == codec and len(records) == 1
        assert records[0].latitude == pytest.approx(41.311081)
        assert records[0].longitude == pytest.approx(69.240562)
        assert records[0].speed_kmh == 25 and records[0].heading_deg == 90
    damaged = bytearray(_frame(0x08, [_record(0x08, now)])); damaged[-1] ^= 1
    with pytest.raises(ValueError, match="CRC"):
        parse_avl_frame(bytes(damaged))


def test_tcp_handshake_codec8_two_records_latest_retry_and_reconnect():
    imei = "555555555555555"
    _device_id, session_id, trip_id = _seed(imei=imei)
    now = datetime.now(timezone.utc)
    frame = _frame(0x08, [_record(0x08, now - timedelta(seconds=5), speed=0),
                          _record(0x08, now, speed=20, lat=41.311181)])
    with _Server():
        with _connect(imei=imei) as sock:
            assert sock.recv(1) == b"\x01"
            for offset in range(0, len(frame), 3):
                sock.sendall(frame[offset:offset + 3])
            assert int.from_bytes(sock.recv(4), "big") == 2
        db = SessionLocal()
        assert db.query(MesTripLocation).filter_by(session_id=session_id).count() == 2
        assert db.get(MesTripLatestLocation, trip_id).latitude == pytest.approx(41.311181)
        assert db.get(MesTrip, trip_id).status == "in_transit"
        db.close()
        with _connect(imei=imei) as sock:  # reconnect and replay exactly the same packet
            assert sock.recv(1) == b"\x01"
            sock.sendall(frame)
            assert int.from_bytes(sock.recv(4), "big") == 2
        db = SessionLocal()
        assert db.query(MesTripLocation).filter_by(session_id=session_id).count() == 2
        db.close()


def test_codec8e_stale_point_does_not_transition():
    imei = "666666666666666"
    _device_id, session_id, trip_id = _seed(imei=imei)
    db = SessionLocal(); trip = db.get(MesTrip, trip_id)
    stale_at = trip.actual_departure_at - timedelta(seconds=1); db.close()
    frame = _frame(0x8E, [_record(0x8E, stale_at.replace(tzinfo=timezone.utc), speed=30)])
    with _Server(), _connect(imei=imei) as sock:
        assert sock.recv(1) == b"\x01"
        sock.sendall(frame)
        assert int.from_bytes(sock.recv(4), "big") == 1
    db = SessionLocal()
    assert db.query(MesTripLocation).filter_by(session_id=session_id).count() == 1
    assert db.get(MesTrip, trip_id).status == "dispatched"
    db.close()


def test_unknown_inactive_invalid_crc_and_multiple_sessions_are_rejected_without_commit():
    _, _, _ = _seed(imei="111111111111111")
    with _Server(), _connect(imei="999999999999999") as sock:
        assert sock.recv(1) == b"\x00"  # explicit rejection, never success ACK

    _, inactive_session, _ = _seed(status="inactive", imei="222222222222222")
    with _Server(), _connect(imei="222222222222222") as sock:
        assert sock.recv(1) == b"\x00"
    db = SessionLocal()
    assert db.query(MesTripLocation).filter_by(session_id=inactive_session).count() == 0
    db.close()

    _device_id, session_id, _ = _seed(imei="333333333333333")
    invalid = bytearray(_frame(0x08, [_record(0x08, datetime.now(timezone.utc))])); invalid[-1] ^= 1
    with _Server(), _connect(imei="333333333333333") as sock:
        assert sock.recv(1) == b"\x01"
        sock.sendall(invalid); assert sock.recv(4) == b""
    db = SessionLocal()
    assert db.query(MesTripLocation).filter_by(session_id=session_id).count() == 0
    db.close()

    device_id, session_id, _ = _seed(imei="444444444444444")
    db = SessionLocal(); original = db.get(MesTripTrackingSession, session_id)
    db.add(MesTripTrackingSession(trip_id=original.trip_id, vehicle_id=original.vehicle_id,
                                  driver_user_id=original.driver_user_id, device_id=device_id,
                                  client_session_id=f"duplicate-{uuid4().hex}", status="active",
                                  authorization_hash="unused",
                                  authorization_expires_at=datetime.utcnow() + timedelta(hours=1)))
    db.commit(); db.close()
    frame = _frame(0x08, [_record(0x08, datetime.now(timezone.utc))])
    with _Server(), _connect(imei="444444444444444") as sock:
        assert sock.recv(1) == b"\x01"
        sock.sendall(frame); assert sock.recv(4) == b""
    db = SessionLocal()
    assert db.query(MesTripLocation).filter_by(session_id=session_id).count() == 0
    db.close()


def test_commit_failure_never_receives_success_record_ack():
    imei = "777777777777777"
    _device_id, session_id, _trip_id = _seed(imei=imei)

    class CommitFailSession:
        def __init__(self):
            self.inner = SessionLocal()

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def commit(self):
            raise RuntimeError("simulated commit failure")

        def rollback(self):
            return self.inner.rollback()

        def close(self):
            return self.inner.close()

    frame = _frame(0x08, [_record(0x08, datetime.now(timezone.utc))])
    with _Server(CommitFailSession), _connect(imei=imei) as sock:
        assert sock.recv(1) == b"\x01"
        sock.sendall(frame)
        assert sock.recv(4) == b""  # no record-count ACK before durable commit
    db = SessionLocal()
    assert db.query(MesTripLocation).filter_by(session_id=session_id).count() == 0
    db.close()
