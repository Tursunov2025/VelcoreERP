"""Phase 12 — GPS fleet tracking smoke test."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="azmus_phase12_"))
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
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-phase12")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from services.seed import seed_defaults  # noqa: E402


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


def main() -> None:
    setup_db()
    client = TestClient(app)
    headers = auth_headers(client)

    v = client.post(
        "/gps/vehicles",
        headers=headers,
        json={"plate_number": "01A777AA", "model": "KamAZ", "status": "active"},
    )
    assert v.status_code == 200, v.text
    vehicle_id = v.json()["id"]

    d = client.post(
        "/gps/drivers",
        headers=headers,
        json={"full_name": "Bekzod Karimov", "phone": "+998901112233", "status": "active"},
    )
    assert d.status_code == 200, d.text
    driver_id = d.json()["id"]

    loc = client.post(
        "/gps/location/update",
        headers=headers,
        json={
            "vehicle_id": vehicle_id,
            "driver_id": driver_id,
            "latitude": 41.311,
            "longitude": 69.279,
            "speed": 62,
            "battery_level": 88,
        },
    )
    assert loc.status_code == 200, loc.text
    assert loc.json()["online"] is True

    latest = client.get("/gps/location/latest", headers=headers)
    assert latest.status_code == 200
    assert len(latest.json()["locations"]) == 1

    transport = client.post(
        "/transports",
        headers=headers,
        json={"vehicle": "KamAZ Export", "driver_name": "Bekzod", "shipment_weight_kg": 5000},
    )
    assert transport.status_code == 200, transport.text
    transport_id = transport.json()["id"]

    trip = client.post(
        "/gps/trips",
        headers=headers,
        json={
            "transport_id": transport_id,
            "vehicle_id": vehicle_id,
            "driver_id": driver_id,
            "origin": "Tashkent",
            "destination": "Almaty",
            "status": "In Transit",
        },
    )
    assert trip.status_code == 200, trip.text

    dash = client.get("/gps/dashboard", headers=headers)
    assert dash.status_code == 200
    assert dash.json()["online_trucks"] >= 1
    assert dash.json()["active_routes"] >= 1

    detail = client.get(f"/transports/{transport_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["gps"] is not None
    assert detail.json()["gps"]["latest"]["latitude"] == 41.311

    hist = client.get(f"/gps/location/history?vehicle_id={vehicle_id}", headers=headers)
    assert hist.status_code == 200
    assert len(hist.json()["history"]) == 1

    print("ALL PHASE 12 GPS SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
