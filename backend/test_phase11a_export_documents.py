"""Phase 11A — export shipments, generated docs, and LLP attachment smoke test."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="azmus_phase11a_"))
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
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-phase11a")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import Document, ExportShipment, ExportShipmentDocument  # noqa: E402
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

    order = client.post(
        "/orders",
        headers=headers,
        json={
            "client": "Kazakhstan Customer",
            "phone": "+7",
            "amount": "12500",
            "destination": "Kazakhstan",
            "comment": "Aluminum export product",
        },
    )
    assert order.status_code == 200, order.text
    order_id = order.json()["id"]

    created = client.post(
        "/export-shipments/from-order",
        headers=headers,
        json={
            "order_id": order_id,
            "country": "Kazakhstan",
            "contract_number": "KZ-2026-001",
            "currency": "USD",
        },
    )
    assert created.status_code == 200, created.text
    shipment = created.json()
    assert shipment["customer"] == "Kazakhstan Customer"
    assert shipment["items"][0]["total_amount"] == 12500

    generated = client.post(
        f"/export-shipments/{shipment['id']}/generate-documents",
        headers=headers,
    )
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["status"] == "Ready"
    assert len(body["documents"]) == 6

    dashboard = client.get("/export-shipments/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["ready"] == 1

    db = SessionLocal()
    try:
        assert db.query(ExportShipment).count() == 1
        assert db.query(ExportShipmentDocument).count() == 6
        assert db.query(Document).filter(Document.title.like("%EXP-%")).count() == 6
    finally:
        db.close()

    for doc in body["documents"]:
        download = client.get(f"/export-shipments/documents/{doc['id']}/download", headers=headers)
        assert download.status_code == 200, download.text
        assert len(download.content) > 100

    print("test_phase11a_export_documents: OK")
    print(f"migration_db={TEST_DB}")
    print(f"uploads={DATA_ROOT / 'uploads'}")


if __name__ == "__main__":
    main()

