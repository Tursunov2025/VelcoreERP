"""Seed the isolated GPS-1 Android device gate database only."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from auth.security import hash_password  # noqa: E402
from config.database_guard import CANONICAL_WINDOWS_DB  # noqa: E402
from config.paths import DB_PATH  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from models import MesTrip, MesVehicle, ProductionProject, ProjectReleaseSnapshot, User, UserPermission  # noqa: E402

USERNAME = "GPS1-DEVICE-DRIVER"
PASSWORD = "Gps1Device-2026!"


def assert_disposable_boundary() -> None:
    resolved = DB_PATH.resolve()
    allowed_root = (BACKEND.parent / ".local-dev" / "gps1-device").resolve()
    if os.getenv("ENVIRONMENT", "").lower() != "test" or os.getenv("DATABASE_GUARD", "").lower() != "false":
        raise RuntimeError("GPS-1 fixture requires ENVIRONMENT=test and DATABASE_GUARD=false")
    if resolved == CANONICAL_WINDOWS_DB.resolve() or allowed_root not in resolved.parents:
        raise RuntimeError(f"Refusing non-disposable database path: {resolved}")


def seed() -> dict[str, object]:
    assert_disposable_boundary()
    Base.metadata.create_all(engine)
    run_migrations()
    run_migrations()
    db = SessionLocal()
    try:
        driver = db.query(User).filter(User.username == USERNAME).one_or_none()
        if driver is None:
            driver = User(username=USERNAME, password_hash=hash_password(PASSWORD), role="driver",
                          department="Logistika", is_active=True, ui_language="uz")
            db.add(driver)
            db.flush()
        else:
            driver.password_hash = hash_password(PASSWORD)
            driver.role = "driver"
            driver.is_active = True
        permission = db.query(UserPermission).filter_by(user_id=driver.id, module="gps_trip_track").one_or_none()
        if permission is None:
            db.add(UserPermission(user_id=driver.id, module="gps_trip_track", enabled=True))
        else:
            permission.enabled = True

        project = db.query(ProductionProject).filter_by(project_code="GPS1-DEVICE-PROJECT").one_or_none()
        if project is None:
            project = ProductionProject(project_code="GPS1-DEVICE-PROJECT", project_name="GPS-1 Device Test",
                customer_name_snapshot="TEST", destination_city="Toshkent", site_name="Atlas",
                full_address="TEST-Toshkent / TEST-Atlas", status="shipped", release_revision=1,
                created_by="gps1-device-fixture")
            db.add(project)
            db.flush()
        release = db.query(ProjectReleaseSnapshot).filter_by(idempotency_key="gps1-device-release-v1").one_or_none()
        if release is None:
            release = ProjectReleaseSnapshot(project_id=project.id, revision=1, source_project_version=1,
                idempotency_key="gps1-device-release-v1", checksum="0" * 64,
                status="released", released_by="gps1-device-fixture")
            db.add(release)
            db.flush()
        vehicle = db.query(MesVehicle).filter_by(registration_number="GPS1TEST").one_or_none()
        if vehicle is None:
            vehicle = MesVehicle(vehicle_type="truck", registration_number="GPS1TEST", max_payload_kg=1000,
                internal_length_mm=4000, internal_width_mm=2000, internal_height_mm=2000,
                created_by="gps1-device-fixture", updated_by="gps1-device-fixture")
            db.add(vehicle)
            db.flush()
        trip = db.query(MesTrip).filter_by(trip_number="GPS1-DEVICE-TRIP").one_or_none()
        if trip is None:
            trip = MesTrip(trip_number="GPS1-DEVICE-TRIP", vehicle_id=vehicle.id, driver_user_id=driver.id,
                project_id=project.id, release_id=release.id, destination_city="Toshkent",
                destination_site="Atlas", destination_address="TEST-Toshkent / TEST-Atlas",
                status="in_transit", created_by="gps1-device-fixture", updated_by="gps1-device-fixture")
            db.add(trip)
        else:
            trip.driver_user_id = driver.id
            trip.status = "in_transit"
        db.commit()
        return {"database": str(DB_PATH.resolve()), "username": USERNAME, "vehicle": vehicle.registration_number,
                "trip": trip.trip_number, "permission": "gps_trip_track"}
    finally:
        db.close()


if __name__ == "__main__":
    print(json.dumps(seed(), ensure_ascii=False))
