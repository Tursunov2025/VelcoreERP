"""Driver location upsert + admin live list."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="azmus_driver_loc_"))
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
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-driver-loc")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import Driver, DriverLocation  # noqa: E402
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

    d = client.post(
        "/gps/drivers",
        headers=headers,
        json={"full_name": "Ali Valiyev", "phone": "+998901234567", "status": "active"},
    )
    assert d.status_code == 200, d.text
    driver_id = d.json()["id"]

    missing = client.post(
        "/api/driver/location",
        headers=headers,
        json={"latitude": 41.31, "longitude": 69.27},
    )
    assert missing.status_code in (400, 422)

    upsert = client.post(
        "/api/driver/location",
        headers=headers,
        json={
            "driver_id": driver_id,
            "latitude": 41.311081,
            "longitude": 69.279737,
            "status": "active",
        },
    )
    assert upsert.status_code == 200, upsert.text
    assert upsert.json()["success"] is True

    upsert2 = client.post(
        "/api/driver/location",
        headers=headers,
        json={
            "driver_id": driver_id,
            "latitude": 41.312,
            "longitude": 69.28,
            "status": "active",
        },
    )
    assert upsert2.status_code == 200, upsert2.text

    db = SessionLocal()
    try:
        count = db.query(DriverLocation).filter(DriverLocation.driver_id == driver_id).count()
        assert count == 1
        row = db.query(DriverLocation).filter(DriverLocation.driver_id == driver_id).one()
        assert abs(row.latitude - 41.312) < 0.001
    finally:
        db.close()

    live = client.get("/api/admin/drivers-live", headers=headers)
    assert live.status_code == 200, live.text
    body = live.json()
    assert body["success"] is True
    assert any(x["driver_id"] == driver_id for x in body["drivers"])
    assert body["drivers"][0]["name"] == "Ali Valiyev"

    db = SessionLocal()
    try:
        row = db.query(DriverLocation).filter(DriverLocation.driver_id == driver_id).one()
        row.status = "offline"
        db.commit()
    finally:
        db.close()

    live2 = client.get("/api/admin/drivers-live", headers=headers)
    assert all(x["driver_id"] != driver_id for x in live2.json()["drivers"])

    db = SessionLocal()
    try:
        row = db.query(DriverLocation).filter(DriverLocation.driver_id == driver_id).one()
        row.status = "active"
        row.last_updated = datetime.utcnow() - timedelta(minutes=10)
        db.commit()
    finally:
        db.close()

    live3 = client.get("/api/admin/drivers-live", headers=headers)
    assert all(x["driver_id"] != driver_id for x in live3.json()["drivers"])

    print("OK — driver location API tests passed")


if __name__ == "__main__":
    main()
