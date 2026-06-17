"""Phase 12.1 — live GPS tracking tests (dedup, dashboard motion buckets)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="azmus_phase121_"))
TEST_DB = TMP / "azmus_test.db"
DATA_ROOT = TMP / "Data"

os.environ["DATA_ROOT"] = str(DATA_ROOT)
os.environ["DB_PATH"] = str(TEST_DB)
os.environ["UPLOAD_PATH"] = str(DATA_ROOT / "uploads")
os.environ["BACKUP_PATH"] = str(DATA_ROOT / "backups")
os.environ["LOG_PATH"] = str(DATA_ROOT / "logs")
os.environ["MIGRATION_BACKUP_PATH"] = str(DATA_ROOT / "migrations")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["DATABASE_GUARD"] = "false"
os.environ["SKIP_DEMO_SEED"] = "true"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-phase121")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from services.gps_fleet import (  # noqa: E402
    DEDUP_DISTANCE_METERS,
    save_location,
)
from services.gps_geocode import city_matches_destination, haversine_meters  # noqa: E402
from services.seed import seed_defaults  # noqa: E402
from models import GpsLocation, Vehicle  # noqa: E402


def setup_db() -> None:
    Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    try:
        seed_defaults(db)
        db.commit()
    finally:
        db.close()


def auth_headers(client: TestClient) -> dict[str, str]:
    r = client.post("/auth/login", json={"username": "admin", "password": "1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_haversine_and_dedup() -> None:
    dist = haversine_meters(41.311, 69.279, 41.31101, 69.27901)
    assert dist < DEDUP_DISTANCE_METERS * 4  # ~1.4m apart

    db = SessionLocal()
    try:
        v = Vehicle(plate_number="TEST01", model="Test", status="active")
        db.add(v)
        db.commit()
        db.refresh(v)

        loc1, saved1 = save_location(
            db,
            vehicle_id=v.id,
            driver_id=None,
            latitude=41.311,
            longitude=69.279,
            speed=40,
            battery_level=90,
        )
        assert saved1 is True
        db.commit()

        loc2, saved2 = save_location(
            db,
            vehicle_id=v.id,
            driver_id=None,
            latitude=41.311001,
            longitude=69.279001,
            speed=41,
            battery_level=89,
        )
        assert saved2 is False
        assert loc2.id == loc1.id

        loc3, saved3 = save_location(
            db,
            vehicle_id=v.id,
            driver_id=None,
            latitude=41.32,
            longitude=69.29,
            speed=55,
            battery_level=88,
        )
        assert saved3 is True
        count = db.query(GpsLocation).filter(GpsLocation.vehicle_id == v.id).count()
        assert count == 2
    finally:
        db.close()


def test_api_dedup_and_dashboard(client: TestClient, headers: dict) -> None:
    v = client.post(
        "/gps/vehicles",
        headers=headers,
        json={"plate_number": "01LIVE99", "model": "Volvo", "status": "active"},
    )
    assert v.status_code == 200
    vehicle_id = v.json()["id"]

    payload = {
        "vehicle_id": vehicle_id,
        "latitude": 41.3,
        "longitude": 69.24,
        "speed": 62,
        "battery_level": 88,
    }
    r1 = client.post("/gps/location/update", headers=headers, json=payload)
    assert r1.status_code == 200
    assert r1.json()["saved"] is True

    r2 = client.post("/gps/location/update", headers=headers, json=payload)
    assert r2.status_code == 200
    assert r2.json()["saved"] is False
    assert r2.json()["duplicate_skipped"] is True

    payload["latitude"] = 41.35
    r3 = client.post("/gps/location/update", headers=headers, json=payload)
    assert r3.status_code == 200
    assert r3.json()["saved"] is True

    hist = client.get(f"/gps/location/history?vehicle_id={vehicle_id}", headers=headers)
    assert len(hist.json()["history"]) == 2

    dash = client.get("/gps/dashboard", headers=headers)
    assert dash.status_code == 200
    body = dash.json()
    assert body["refresh_interval_sec"] == 5
    assert "moving_vehicles" in body
    assert "stopped_vehicles" in body
    assert body["online_trucks"] >= 1


def test_city_match() -> None:
    assert city_matches_destination("Almaty", "Almaty, Kazakhstan")
    assert city_matches_destination("Tashkent", "Toshkent")


def main() -> None:
    setup_db()
    test_haversine_and_dedup()
    test_city_match()

    client = TestClient(app)
    headers = auth_headers(client)
    test_api_dedup_and_dashboard(client, headers)

    print("ALL PHASE 12.1 LIVE GPS TESTS PASSED")


if __name__ == "__main__":
    main()
