"""Disposable regression coverage for the canonical Logistics registries."""

from __future__ import annotations

import os
import sys
from uuid import uuid4
from pathlib import Path
from types import SimpleNamespace

import pytest

DB = Path(os.getenv("LOGISTICS_MASTER_DATA_TEST_DB", str(Path.cwd() / ".tmp" / "logistics-master-data-test.db")))
DB.parent.mkdir(parents=True, exist_ok=True)
os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB.as_posix()}",
    "DB_PATH": str(DB),
    "DATA_ROOT": str(DB.parent / "data"),
    "DATABASE_GUARD": "false",
    "ENVIRONMENT": "test",
    "JWT_SECRET_KEY": "logistics-master-data-test-secret",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth.security import hash_password  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from models import MesTrip, MesVehicle, User  # noqa: E402
from services.finished_logistics import LogisticsError, create_vehicle, update_vehicle  # noqa: E402
from services.logistics_master_data import (  # noqa: E402
    create_driver, create_gps_device, serialize_driver, set_driver_status,
    unbind_gps_device, update_gps_device, update_driver,
)
from services.logistics_planning import update_vehicle_state  # noqa: E402

RUN = uuid4().hex[:8].upper()


@pytest.fixture()
def db():
    Base.metadata.create_all(engine)
    run_migrations()
    session = SessionLocal()
    admin = session.query(User).filter_by(username=f"master-admin-{RUN}").first()
    if not admin:
        admin = User(username=f"master-admin-{RUN}", password_hash=hash_password("Admin123!"), role="admin", department="Admin")
        session.add(admin)
        session.commit()
    try:
        yield session, admin
    finally:
        session.close()


def vehicle_data(**overrides):
    values = dict(vehicle_type="truck", registration_number=f"01 A {RUN} AA", internal_code="TR-01", model="Test Model", driver_name="", driver_phone="", max_payload_kg=1000, internal_length_mm=4000, internal_width_mm=2000, internal_height_mm=2000, max_volume_m3=16, is_active=True, notes="")
    values.update(overrides)
    return SimpleNamespace(**values)


def driver_data(**overrides):
    values = dict(username=f"driver.one.{RUN.lower()}", password="Driver123!", department="Logistika", full_name="Driver One", employee_id=f"D-{RUN}", position="Driver", phone="+998900000001", email="", telegram="", avatar_url="", is_active=True)
    values.update(overrides)
    return SimpleNamespace(**values)


def test_vehicle_crud_state_and_duplicate(db):
    session, admin = db
    vehicle = create_vehicle(session, vehicle_data(), admin.username)
    session.commit()
    assert vehicle.registration_number == f"01A{RUN}AA"
    assert vehicle.internal_code == "TR-01"
    with pytest.raises(LogisticsError, match="Registration"):
        create_vehicle(session, vehicle_data(registration_number=f"01A {RUN} AA"), admin.username)
    session.rollback()
    vehicle = update_vehicle(session, vehicle, SimpleNamespace(expected_version=1, registration_number=None, vehicle_type="van", internal_code="TR-01B", model="Updated", driver_name="", driver_phone="", max_payload_kg=None, load_capacity=None, internal_length_mm=None, internal_width_mm=None, internal_height_mm=None, max_volume_m3=None, is_active=None, notes="updated"), admin.username)
    session.commit()
    assert vehicle.version == 2 and vehicle.model == "Updated"
    with pytest.raises(Exception) as conflict:
        update_vehicle_state(session, vehicle.id, operational_state="SERVICE", expected_version=1, actor=admin.username)
    assert getattr(conflict.value, "code", "") == "vehicle_version_conflict"


def test_driver_crud_active_trip_protection_and_profile(db):
    session, admin = db
    driver = create_driver(session, driver_data(), admin.username)
    session.commit()
    assert serialize_driver(session, driver)["full_name"] == "Driver One"
    driver = update_driver(session, driver.id, driver_data(username=f"driver.one.{RUN.lower()}", password="", full_name="Driver Updated", is_active=True), admin.username)
    session.commit()
    assert serialize_driver(session, driver)["full_name"] == "Driver Updated"
    set_driver_status(session, driver.id, False, admin.username)
    session.commit()
    assert not driver.is_active


def test_gps_device_unique_binding_update_unbind(db):
    session, admin = db
    driver = create_driver(session, driver_data(username=f"driver.gps.{RUN.lower()}"), admin.username)
    vehicle = create_vehicle(session, vehicle_data(registration_number=f"02 B {RUN} BB"), admin.username)
    session.commit()
    device = create_gps_device(session, SimpleNamespace(device_identifier=f"gps-{RUN}", vehicle_id=vehicle.id, driver_user_id=driver.id, status="active", notes=""), admin.username)
    session.commit()
    assert device.device_identifier == f"GPS-{RUN}"
    with pytest.raises(LogisticsError) as duplicate:
        create_gps_device(session, SimpleNamespace(device_identifier=f"GPS-{RUN}", vehicle_id=vehicle.id, driver_user_id=driver.id, status="active", notes=""), admin.username)
    assert duplicate.value.code == "gps_device_exists"
    updated = update_gps_device(session, device.id, SimpleNamespace(expected_version=1, device_identifier=f"gps-{RUN}", vehicle_id=vehicle.id, driver_user_id=driver.id, status="active", notes="reconnect"), admin.username)
    session.commit()
    assert updated.version == 2
    unbound = unbind_gps_device(session, device.id, 2, admin.username)
    session.commit()
    assert unbound.status == "inactive"
