"""GPS-1 canonical trip tracking on disposable SQLite."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
ROOT = Path(tempfile.mkdtemp(prefix="velcore-gps1-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB.replace(chr(92), '/')}", "DB_PATH": DB,
    "DATA_ROOT": str(ROOT), "DATABASE_GUARD": "false", "ENVIRONMENT": "test",
    "JWT_SECRET_KEY": "gps1-test-secret",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from auth.security import create_access_token  # noqa: E402
from main import app  # noqa: E402
from models import (MesGpsDevice, MesTrip, MesTripLatestLocation, MesTripLocation, MesTripTrackingSession, MesVehicle,
                    ProductionProject, ProjectReleaseSnapshot, User, UserPermission)  # noqa: E402
from services.trip_tracking import (TripTrackingError, append_locations, cleanup_history,
                                    effective_health, gps_policy, heartbeat, require_assigned_trip,
                                    revoke_session, start_session, stop_session)  # noqa: E402
from services.trip_lifecycle import TripLifecycleError, confirm_arrival  # noqa: E402
from services.logistics_planning import derive_trip_alerts  # noqa: E402


def setup_module():
    Base.metadata.create_all(engine)
    run_migrations(); run_migrations()


def teardown_module():
    engine.dispose()
    Path(DB).unlink(missing_ok=True)
    shutil.rmtree(ROOT, ignore_errors=True)


def _fixture():
    db = SessionLocal()
    suffix = uuid4().hex[:8]
    driver = User(username=f"gps-driver-{suffix}", role="driver", department="Logistika")
    other = User(username=f"other-driver-{suffix}", role="driver", department="Logistika")
    project = ProductionProject(project_code=f"GPS1-{suffix}", project_name="GPS 1", customer_name_snapshot="TEST",
                                destination_city="Toshkent", site_name="Atlas", full_address="TEST Atlas",
                                status="shipped", release_revision=1, created_by="test")
    vehicle = MesVehicle(vehicle_type="truck", registration_number=f"GPS{suffix}", max_payload_kg=1000,
                         internal_length_mm=4000, internal_width_mm=2000, internal_height_mm=2000,
                         created_by="test", updated_by="test")
    db.add_all([driver, other, project, vehicle]); db.flush()
    release = ProjectReleaseSnapshot(project_id=project.id, revision=1, source_project_version=1,
                                     idempotency_key=f"gps-release-{suffix}", checksum="0" * 64, released_by="test")
    db.add(release); db.flush()
    trip = MesTrip(trip_number=f"GPS-TRIP-{suffix}", vehicle_id=vehicle.id, driver_user_id=driver.id,
                   project_id=project.id, release_id=release.id, destination_city="Toshkent",
                   destination_site="Atlas", destination_address="TEST Atlas", status="in_transit",
                   created_by="test", updated_by="test")
    db.add(trip); db.commit()
    return db, driver, other, trip


def test_session_idor_offline_batch_and_idempotency():
    db, driver, other, trip = _fixture()
    try:
        try:
            require_assigned_trip(db, trip.id, other)
            assert False, "cross-driver trip was exposed"
        except TripTrackingError as exc:
            assert exc.status_code == 404

        session, token = start_session(db, trip.id, driver, "gps1-session-0001")
        db.commit()
        retry, retry_token = start_session(db, trip.id, driver, "gps1-session-0001")
        assert retry.id == session.id
        token = retry_token
        captured = datetime.utcnow() - timedelta(minutes=2)
        point = {"client_point_id": "gps1-point-0001", "latitude": 41.311081,
                 "longitude": 69.240562, "accuracy_m": 8, "speed_kmh": 35,
                 "heading_deg": 90, "battery_level": 72, "captured_at": captured,
                 "was_queued": True}
        first = append_locations(db, session.id, driver, token, [point]); db.commit()
        second = append_locations(db, session.id, driver, token, [point]); db.commit()
        assert first["accepted"] == 1 and second["accepted"] == 0 and second["duplicates"] == 1
        assert db.query(MesTripLocation).filter_by(session_id=session.id).count() == 1
        assert db.query(MesTripLocation).filter_by(session_id=session.id).one().was_queued is True
        stopped = stop_session(db, session.id, driver, token); db.commit()
        assert stopped.status == "stopped"
        assert stop_session(db, session.id, driver, token).status == "stopped"
    finally:
        db.close()


def test_consecutive_timezone_aware_points_use_one_sqlite_time_basis():
    db, driver, _, trip = _fixture()
    try:
        session, token = start_session(db, trip.id, driver, "gps1-aware-session")
        db.commit()
        first = {
            "client_point_id": "gps1-aware-point-1",
            "latitude": 41.31,
            "longitude": 69.24,
            "captured_at": datetime.now(timezone.utc) - timedelta(seconds=5),
            "was_queued": False,
        }
        second = {
            **first,
            "client_point_id": "gps1-aware-point-2",
            "captured_at": datetime.now(timezone.utc),
        }
        assert append_locations(db, session.id, driver, token, [first])["accepted"] == 1
        db.commit()
        db.expire_all()
        assert append_locations(db, session.id, driver, token, [second])["accepted"] == 1
        db.commit()
        assert append_locations(db, session.id, driver, token, [second])["duplicates"] == 1
        latest = db.get(MesTripLatestLocation, trip.id)
        assert latest.captured_at == second["captured_at"].replace(tzinfo=None)
    finally:
        db.close()


def test_stopped_session_and_invalid_coordinates_rejected():
    db, driver, _, trip = _fixture()
    try:
        session, token = start_session(db, trip.id, driver, "gps1-session-0002")
        stop_session(db, session.id, driver, token); db.commit()
        try:
            append_locations(db, session.id, driver, token, [{"client_point_id": "gps1-point-0002",
                "latitude": 91, "longitude": 0, "captured_at": datetime.utcnow(), "was_queued": False}])
            assert False, "stopped session accepted a point"
        except TripTrackingError as exc:
            assert exc.code == "tracking_session_stopped"
    finally:
        db.close()


def test_api_permission_and_cross_driver_idor():
    db, driver, other, trip = _fixture()
    try:
        db.add_all([
            UserPermission(user_id=driver.id, module="gps_trip_track", enabled=True),
            UserPermission(user_id=other.id, module="gps_trip_track", enabled=True),
        ]); db.commit()
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {create_access_token({'sub': driver.username})}"}
        denied_headers = {"Authorization": f"Bearer {create_access_token({'sub': other.username})}"}
        assert client.get("/mes/finished-logistics/driver/trips/active", headers=headers).json()["trips"][0]["id"] == trip.id
        response = client.post(f"/mes/finished-logistics/trips/{trip.id}/tracking/start",
                               json={"client_session_id": "api-session-0001"}, headers=denied_headers)
        assert response.status_code == 404 and response.json()["detail"]["code"] == "trip_not_found"
        no_permission = User(username=f"no-gps-{uuid4().hex[:8]}", role="operator", department="Kesish")
        db.add(no_permission); db.commit()
        response = client.get("/mes/finished-logistics/driver/trips/active", headers={
            "Authorization": f"Bearer {create_access_token({'sub': no_permission.username})}"})
        assert response.status_code == 403
        assert client.get("/mes/finished-logistics/tracking/fleet").status_code == 401
        start = client.post(f"/mes/finished-logistics/trips/{trip.id}/tracking/start",
                            json={"client_session_id":"api-valid-session"},headers=headers)
        assert start.status_code == 200
        auth=start.json()["tracking_authorization"];session_id=start.json()["id"]
        invalid_points=[
            {"latitude":91,"longitude":0}, {"latitude":0,"longitude":181},
            {"latitude":0,"longitude":0,"accuracy_m":-1}, {"latitude":0,"longitude":0,"speed_kmh":-1},
            {"latitude":0,"longitude":0,"heading_deg":360}, {"latitude":0,"longitude":0,"battery_level":101},
        ]
        for index,extra in enumerate(invalid_points):
            point={"client_point_id":f"api-invalid-{index:04d}","latitude":0,"longitude":0,"captured_at":datetime.utcnow().isoformat(),**extra}
            response=client.post(f"/mes/finished-logistics/tracking/sessions/{session_id}/locations",json={"points":[point]},headers={**headers,"X-Tracking-Authorization":auth})
            assert response.status_code==422
    finally:
        db.close()


def test_authorization_expiry_revocation_scope_and_audit_redaction():
    db, driver, other, trip = _fixture()
    try:
        session, token = start_session(db, trip.id, driver, "hardening-session-1"); db.commit()
        assert token not in str(db.query(MesTripTrackingSession).filter_by(id=session.id).one().__dict__)
        session.authorization_expires_at = datetime.utcnow() - timedelta(seconds=1); db.commit()
        try: append_locations(db, session.id, driver, token, [])
        except TripTrackingError as exc: assert exc.code == "tracking_authorization_expired"
        session.authorization_expires_at = datetime.utcnow() + timedelta(minutes=5); db.commit()
        revoke_session(db, session.id, other); db.commit()
        try: append_locations(db, session.id, driver, token, [])
        except TripTrackingError as exc: assert exc.code == "tracking_authorization_revoked"
        from models import AuditLog
        assert token not in " ".join(row.details or "" for row in db.query(AuditLog).all())
    finally: db.close()


def test_validation_conflict_out_of_order_latest_nulls_health_and_retention():
    db, driver, _, trip = _fixture()
    try:
        session, token = start_session(db, trip.id, driver, "hardening-session-2"); db.commit()
        now=datetime.utcnow(); newer={"client_point_id":"hardening-point-1","latitude":41.3,"longitude":69.2,"accuracy_m":None,"speed_kmh":None,"heading_deg":None,"battery_level":None,"captured_at":now,"was_queued":False}
        older={**newer,"client_point_id":"hardening-point-2","latitude":41.2,"captured_at":now-timedelta(minutes=2),"was_queued":True}
        append_locations(db,session.id,driver,token,[newer,older]);db.commit()
        latest=db.get(MesTripLatestLocation,trip.id);assert latest.latitude==41.3 and latest.accuracy_m is None and latest.speed_kmh is None
        assert append_locations(db,session.id,driver,token,[newer])["duplicates"]==1
        conflict={**newer,"latitude":40.0}
        try:append_locations(db,session.id,driver,token,[conflict])
        except TripTrackingError as exc:assert exc.code=="tracking_client_point_conflict"
        heartbeat(db,session.id,driver,token,"syncing",7,None,48);db.commit();assert session.queued_point_count==7
        session.last_contact_at=now-timedelta(hours=1);assert effective_health(session,gps_policy(db),now)=="stale"
        old=db.query(MesTripLocation).filter_by(client_point_id="hardening-point-2").one();old.captured_at=now-timedelta(days=100);db.commit()
        assert cleanup_history(db,now)>=1
    finally:db.close()


def test_time_windows_and_finalized_trip_block_tracking():
    db, driver, _, trip = _fixture()
    try:
        session,token=start_session(db,trip.id,driver,"hardening-session-3");db.commit()
        base={"client_point_id":"hardening-point-3","latitude":0,"longitude":0,"accuracy_m":0,"speed_kmh":0,"heading_deg":0,"battery_level":0,"was_queued":False}
        for captured in (datetime.utcnow()-timedelta(hours=73),datetime.utcnow()+timedelta(minutes=6)):
            try:append_locations(db,session.id,driver,token,[{**base,"captured_at":captured}]);assert False
            except TripTrackingError as exc:assert exc.code=="tracking_time_out_of_range"
        trip.status="delivered";db.commit()
        try:append_locations(db,session.id,driver,token,[{**base,"captured_at":datetime.utcnow()}]);assert False
        except TripTrackingError as exc:assert exc.code=="tracking_scope_mismatch"
    finally:db.close()


def test_phase4_gps_lifecycle_and_manual_arrival_idempotency():
    db, driver, _, trip = _fixture()
    try:
        departure = datetime.utcnow() - timedelta(seconds=5)
        trip.status = "dispatched"; trip.actual_departure_at = departure; db.commit()
        device = MesGpsDevice(device_identifier="356307042441013", vehicle_id=trip.vehicle_id,
                              driver_user_id=driver.id, status="active", created_by="test", updated_by="test")
        db.add(device); db.commit()
        session, token = start_session(db, trip.id, driver, f"phase4-{uuid4().hex}", device.device_identifier); db.commit()
        assert session.device_id == device.id and session.vehicle_id == trip.vehicle_id and session.driver_user_id == driver.id
        stale = {"client_point_id": f"stale-{uuid4().hex}", "latitude": 41.0, "longitude": 69.0,
                 "accuracy_m": 10, "speed_kmh": 0, "heading_deg": 0, "battery_level": 80,
                 "captured_at": departure - timedelta(seconds=1), "was_queued": False}
        append_locations(db, session.id, driver, token, [stale]); db.commit()
        assert db.get(MesTrip, trip.id).status == "dispatched"
        moving = {**stale, "client_point_id": f"moving-{uuid4().hex}",
                  "captured_at": datetime.utcnow(), "speed_kmh": 18}
        append_locations(db, session.id, driver, token, [moving]); db.commit()
        trip = db.get(MesTrip, trip.id); assert trip.status == "in_transit"
        assert "ARRIVAL_CONFIRMATION_PENDING" in {x["type"] for x in derive_trip_alerts(db, trip)}
        key = f"arrival-{uuid4().hex}"
        arrival_version = trip.version
        first = confirm_arrival(db, trip.id, expected_version=arrival_version, idempotency_key=key, actor=driver.username); db.commit()
        retry = confirm_arrival(db, trip.id, expected_version=arrival_version, idempotency_key=key, actor=driver.username)
        assert first["status"] == "arrived" and retry["idempotent"] is True
        trip = db.get(MesTrip, trip.id)
        assert "DELIVERY_CONFIRMATION_PENDING" in {x["type"] for x in derive_trip_alerts(db, trip)}
        try:
            confirm_arrival(db, trip.id, expected_version=trip.version,
                            idempotency_key=f"again-{uuid4().hex}", actor=driver.username)
            assert False, "duplicate arrival with a new command was accepted"
        except TripLifecycleError as exc:
            assert exc.code == "invalid_trip_transition"
    finally: db.close()
