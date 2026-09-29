"""Disposable H02 parser and real TCP socket integration acceptance."""
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
ROOT = Path(tempfile.mkdtemp(prefix="velcore-sinotrack-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB.replace(chr(92), '/')}", "DB_PATH": DB,
    "DATA_ROOT": str(ROOT), "DATABASE_GUARD": "false", "ENVIRONMENT": "test",
    "JWT_SECRET_KEY": "sinotrack-test-secret",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from models import (MesGpsDevice, MesTrip, MesTripLatestLocation, MesTripLocation,
                    MesTripTrackingSession, MesVehicle, ProductionProject,
                    ProjectReleaseSnapshot, User)  # noqa: E402
from services.sinotrack_h02 import H02ProtocolError, parse_h02_packet  # noqa: E402
from services.sinotrack_tcp_server import SinoTrackTcpServer  # noqa: E402


def setup_module():
    Base.metadata.create_all(engine)
    run_migrations(); run_migrations()


def teardown_module():
    engine.dispose()
    Path(DB).unlink(missing_ok=True)
    shutil.rmtree(ROOT, ignore_errors=True)


def _seed(identifier: str, *, device_status="active"):
    db = SessionLocal(); suffix = uuid4().hex[:8]
    driver = User(username=f"sino-driver-{suffix}", role="driver", department="Logistika")
    project = ProductionProject(project_code=f"SINO-{suffix}", project_name="SinoTrack test",
                                customer_name_snapshot="TEST", destination_city="Toshkent",
                                site_name="Atlas", full_address="TEST Atlas", status="shipped",
                                release_revision=1, created_by="test")
    vehicle = MesVehicle(vehicle_type="truck", registration_number=f"SINO{suffix}",
                         max_payload_kg=1000, internal_length_mm=4000,
                         internal_width_mm=2000, internal_height_mm=2000,
                         created_by="test", updated_by="test")
    db.add_all([driver, project, vehicle]); db.flush()
    release = ProjectReleaseSnapshot(project_id=project.id, revision=1, source_project_version=1,
                                     idempotency_key=f"release-{suffix}", checksum="0" * 64,
                                     released_by="test")
    db.add(release); db.flush()
    departure = datetime.utcnow() - timedelta(minutes=2)
    trip = MesTrip(trip_number=f"SINO-TRIP-{suffix}", vehicle_id=vehicle.id,
                   driver_user_id=driver.id, project_id=project.id, release_id=release.id,
                   destination_city="Toshkent", destination_site="Atlas",
                   destination_address="TEST Atlas", status="dispatched",
                   actual_departure_at=departure, created_by="test", updated_by="test")
    db.add(trip); db.flush()
    device = MesGpsDevice(device_identifier=identifier, vehicle_id=vehicle.id,
                          driver_user_id=driver.id, status=device_status,
                          created_by="test", updated_by="test")
    db.add(device); db.flush()
    session = MesTripTrackingSession(trip_id=trip.id, vehicle_id=vehicle.id,
                                     driver_user_id=driver.id, device_id=device.id,
                                     client_session_id=f"sino-session-{suffix}", status="active",
                                     authorization_hash="not-exposed-to-tracker",
                                     authorization_expires_at=datetime.utcnow() + timedelta(hours=1))
    db.add(session); db.commit()
    result = device.id, session.id, trip.id, departure
    db.close(); return result


def _packet(identifier: str, captured: datetime, *, validity="A", lat="4120.0000", ns="N",
            lon="06915.0000", ew="E", speed="10.00", heading="90", extras="FFFFFBFF") -> bytes:
    captured = captured.astimezone(timezone.utc)
    return (f"*HQ,{identifier},V1,{captured:%H%M%S},{validity},{lat},{ns},{lon},{ew},"
            f"{speed},{heading},{captured:%d%m%y},{extras}#").encode("ascii")


def _wait_for_count(session_id: int, expected: int):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        db = SessionLocal(); count = db.query(MesTripLocation).filter_by(session_id=session_id).count(); db.close()
        if count == expected:
            return
        time.sleep(0.02)
    raise AssertionError(f"expected {expected} locations, got {count}")


class _Server:
    def __enter__(self):
        self.server = SinoTrackTcpServer(("127.0.0.1", 8502), SessionLocal)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start(); return self.server

    def __exit__(self, *_args):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)


def test_parser_identifier_coordinates_validity_and_optional_fields():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    north_east = parse_h02_packet(_packet("1234567890", now, extras="FFFFFBFF,134,02,2349,0"))
    assert north_east.identifier == "1234567890" and north_east.gps_valid is True
    assert north_east.point["latitude"] == pytest.approx(41 + 20 / 60)
    assert north_east.point["longitude"] == pytest.approx(69 + 15 / 60)
    assert north_east.point["speed_kmh"] == pytest.approx(18.52)
    south_west = parse_h02_packet(_packet("123456789012345", now, ns="S", ew="W"))
    assert south_west.point["latitude"] < 0 and south_west.point["longitude"] < 0
    invalid_fix = parse_h02_packet(_packet("123", now, validity="V", lat="", lon=""))
    assert invalid_fix.gps_valid is False and invalid_fix.point is None
    heartbeat = parse_h02_packet(b"*HQ,1234567890,HTBT,75,optional#")
    assert heartbeat.message_type == "HTBT" and heartbeat.point is None
    with pytest.raises(H02ProtocolError):
        parse_h02_packet(b"*HQ,tracker-name,V0#")


def test_fragmented_tcp_mixed_heartbeat_location_latest_and_fresh_transition():
    identifier = "5100000001"
    _device_id, session_id, trip_id, _departure = _seed(identifier)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    heartbeat = f"*HQ,{identifier},V0#".encode("ascii")
    first = _packet(identifier, now - timedelta(seconds=5), speed="0.00")
    second = _packet(identifier, now, lat="4120.0600", speed="12.00")
    with _Server():
        with socket.create_connection(("127.0.0.1", 8502), timeout=2) as sock:
            for byte in heartbeat + first:  # fragmented framing
                sock.sendall(bytes([byte]))
            assert sock.recv(256) == heartbeat
            sock.sendall(second + heartbeat)  # multiple packets in one write
            assert sock.recv(256) == heartbeat
            _wait_for_count(session_id, 2)
    db = SessionLocal()
    latest = db.get(MesTripLatestLocation, trip_id)
    assert latest.location_id == db.query(MesTripLocation).filter_by(session_id=session_id).order_by(
        MesTripLocation.captured_at.desc()).first().id
    assert db.get(MesTrip, trip_id).status == "in_transit"
    db.close()


def test_duplicate_reconnect_is_idempotent_and_stale_does_not_transition():
    identifier = "510000000000002"
    _device_id, session_id, trip_id, departure = _seed(identifier)
    stale = _packet(identifier, (departure - timedelta(seconds=1)).replace(tzinfo=timezone.utc), speed="20.00")
    with _Server():
        for _ in range(2):
            with socket.create_connection(("127.0.0.1", 8502), timeout=2) as sock:
                sock.sendall(stale)
                _wait_for_count(session_id, 1)
    db = SessionLocal()
    assert db.query(MesTripLocation).filter_by(session_id=session_id).count() == 1
    assert db.get(MesTrip, trip_id).status == "dispatched"
    db.close()


def test_unknown_inactive_invalid_fix_and_connection_identifier_change_are_safe():
    active_id = "5200000001"; inactive_id = "520000000000002"
    _device_id, active_session, _trip_id, _ = _seed(active_id)
    _seed(inactive_id, device_status="inactive")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with _Server():
        for identifier in ("999999999", inactive_id):
            with socket.create_connection(("127.0.0.1", 8502), timeout=2) as sock:
                sock.sendall(_packet(identifier, now)); assert sock.recv(1) == b""
        with socket.create_connection(("127.0.0.1", 8502), timeout=2) as sock:
            sock.sendall(_packet(active_id, now, validity="V", lat="", lon=""))
            time.sleep(0.05)
        with socket.create_connection(("127.0.0.1", 8502), timeout=2) as sock:
            sock.sendall(f"*HQ,{active_id},V0#*HQ,999999999,V0#".encode("ascii"))
            assert sock.recv(256) == f"*HQ,{active_id},V0#".encode("ascii")
            assert sock.recv(1) == b""
    db = SessionLocal()
    assert db.query(MesTripLocation).filter_by(session_id=active_session).count() == 0
    db.close()


def test_multiple_active_sessions_block_location():
    identifier = "5300000001"
    device_id, session_id, _trip_id, _ = _seed(identifier)
    db = SessionLocal(); original = db.get(MesTripTrackingSession, session_id)
    db.add(MesTripTrackingSession(trip_id=original.trip_id, vehicle_id=original.vehicle_id,
                                  driver_user_id=original.driver_user_id, device_id=device_id,
                                  client_session_id=f"duplicate-{uuid4().hex}", status="active",
                                  authorization_hash="unused",
                                  authorization_expires_at=datetime.utcnow() + timedelta(hours=1)))
    db.commit(); db.close()
    with _Server(), socket.create_connection(("127.0.0.1", 8502), timeout=2) as sock:
        sock.sendall(_packet(identifier, datetime.now(timezone.utc))); assert sock.recv(1) == b""
    db = SessionLocal()
    assert db.query(MesTripLocation).filter_by(session_id=session_id).count() == 0
    db.close()
