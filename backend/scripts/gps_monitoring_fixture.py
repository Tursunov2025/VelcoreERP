"""Seed the disposable four-state GPS monitoring acceptance fleet."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if not (os.getenv("DATABASE_URL") or "").startswith("sqlite") or os.getenv("ENVIRONMENT") != "test":
    raise SystemExit("GPS monitoring fixture requires explicit disposable SQLite and ENVIRONMENT=test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auth.security import hash_password  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from models import (MesGpsDevice, MesTrip, MesTripTrackingSession, MesVehicle,
                    ProductionProject, ProjectReleaseSnapshot, User,
                    UserIdentityProfile, UserPermission)  # noqa: E402
from services.trip_tracking import append_locations_for_session  # noqa: E402


def main():
    Base.metadata.create_all(engine); run_migrations(); db = SessionLocal(); now = datetime.utcnow()
    admin = User(username="gps-monitor-admin", password_hash=hash_password("GpsMonitor!2026"), role="admin", department="Logistika", is_active=True)
    db.add(admin); db.flush()
    db.add_all([UserPermission(user_id=admin.id, module=permission, enabled=True) for permission in ("gps_trip_view", "mes_terminal_dispatch", "logistics_master_manage")])
    project = ProductionProject(project_code="GPS-MONITOR-TEST", project_name="GPS Monitoring", customer_name_snapshot="TEST", destination_city="Toshkent", site_name="Atlas", full_address="TEST Atlas", status="shipped", release_revision=1, created_by=admin.username)
    db.add(project); db.flush()
    release = ProjectReleaseSnapshot(project_id=project.id, revision=1, source_project_version=1, idempotency_key="gps-monitor-release", checksum="0" * 64, released_by=admin.username)
    db.add(release); db.flush()
    states = [
        ("01 MOVE 001", "Moving Truck", "Driver Moving", "+998900000001", "5900000001", "sinotrack_h02", "dispatched", 28.0, now - timedelta(seconds=15)),
        ("01 STOP 002", "Stopped Van", "Driver Stopped", "+998900000002", "5900000002", "sinotrack_h02", "loaded", 0.0, now - timedelta(seconds=25)),
        ("01 OFF 003", "Offline Truck", "Driver Offline", "+998900000003", "5900000003", "teltonika_avl", "dispatched", 12.0, now - timedelta(minutes=12)),
        ("01 NOGPS 04", "Reserve Vehicle", "", "", None, None, None, None, None),
    ]
    for index, (plate, model, driver_name, phone, identifier, protocol, trip_status, speed, captured) in enumerate(states, 1):
        vehicle = MesVehicle(vehicle_type="truck", registration_number=plate, model=model, driver_name=driver_name, driver_phone=phone, max_payload_kg=1500, internal_length_mm=4500, internal_width_mm=2100, internal_height_mm=2100, operational_state="AVAILABLE", created_by=admin.username, updated_by=admin.username)
        db.add(vehicle); db.flush()
        if not identifier: continue
        driver = User(username=f"gps-driver-{index}", password_hash=hash_password("Driver!2026"), role="driver", department="Logistika", is_active=True)
        db.add(driver); db.flush(); db.add(UserIdentityProfile(user_id=driver.id, full_name=driver_name, phone=phone))
        trip = MesTrip(trip_number=f"GPS-MON-{index}", vehicle_id=vehicle.id, driver_user_id=driver.id, driver_name_snapshot=driver_name, driver_phone_snapshot=phone, project_id=project.id, release_id=release.id, destination_city="Toshkent", destination_site=f"TEST-{index}", destination_address=f"TEST address {index}", status=trip_status, actual_departure_at=now - timedelta(minutes=5), delivery_deadline_at=now + timedelta(hours=2), created_by=admin.username, updated_by=admin.username)
        db.add(trip); db.flush()
        device = MesGpsDevice(device_identifier=identifier, vehicle_id=vehicle.id, driver_user_id=driver.id, protocol=protocol, status="active", created_by=admin.username, updated_by=admin.username)
        db.add(device); db.flush()
        session = MesTripTrackingSession(trip_id=trip.id, vehicle_id=vehicle.id, driver_user_id=driver.id, device_id=device.id, client_session_id=f"gps-monitor-session-{index}", status="active", authorization_hash="fixture-only", authorization_expires_at=now + timedelta(hours=4), last_contact_at=captured, health_state="active")
        db.add(session); db.flush()
        point = {"client_point_id":f"gps-monitor-point-{index}", "latitude":41.30 + index * .01, "longitude":69.20 + index * .01, "accuracy_m":None, "speed_kmh":speed, "heading_deg":90.0 + index, "battery_level":None, "captured_at":captured.replace(tzinfo=timezone.utc), "was_queued":True}
        append_locations_for_session(db, session, [point])
        session.last_contact_at = captured
    db.commit(); db.close()
    print("gps-monitor-admin / GpsMonitor!2026")


if __name__ == "__main__": main()
