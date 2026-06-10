"""Phase 11B — currency, transport, debt ledger, forecast and KPI smoke test."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="azmus_phase11b_"))
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
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-phase11b")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import Material, MaterialIssue  # noqa: E402
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


def test_currencies(client: TestClient, headers: dict) -> None:
    r = client.get("/currencies", headers=headers)
    assert r.status_code == 200, r.text
    codes = {c["code"] for c in r.json()["currencies"]}
    assert {"UZS", "KZT", "USD", "RUB"} <= codes, codes

    # Add rates: 1 USD = 12500 UZS, 1 KZT = 25 UZS
    for code, rate in (("USD", 12500), ("KZT", 25)):
        r = client.post(
            "/currencies/rates",
            headers=headers,
            json={"currency_code": code, "rate_to_base": rate},
        )
        assert r.status_code == 200, r.text

    # History
    r = client.get("/currencies/rates/history?currency_code=USD", headers=headers)
    assert r.status_code == 200 and len(r.json()["history"]) == 1

    # Conversion: 100 USD -> KZT = 100 * 12500 / 25 = 50000
    r = client.get("/currencies/convert?amount=100&from=USD&to=KZT", headers=headers)
    assert r.status_code == 200, r.text
    assert abs(r.json()["converted"] - 50000) < 0.01, r.json()

    # Dashboard widget
    r = client.get("/currencies/dashboard", headers=headers)
    assert r.status_code == 200
    usd = next(x for x in r.json()["rates"] if x["code"] == "USD")
    assert usd["rate_to_base"] == 12500
    print("PASS currencies: table, rates, history, conversion, dashboard")


def test_transport(client: TestClient, headers: dict) -> None:
    r = client.post(
        "/transports",
        headers=headers,
        json={
            "vehicle": "KamAZ 01 A 777 AA",
            "driver_name": "Bekzod",
            "driver_phone": "+998901112233",
            "shipment_weight_kg": 1200,
        },
    )
    assert r.status_code == 200, r.text
    transport = r.json()
    assert transport["status"] == "Draft"
    assert len(transport["events"]) == 1

    for status in ("Loaded", "In Transit", "Border", "Delivered"):
        r = client.post(
            f"/transports/{transport['id']}/status",
            headers=headers,
            json={"status": status, "comment": f"-> {status}"},
        )
        assert r.status_code == 200, r.text
    final = r.json()
    assert final["status"] == "Delivered"
    assert len(final["events"]) == 5
    assert final["departure_date"] and final["arrival_date"]

    r = client.get("/transports/dashboard", headers=headers)
    assert r.status_code == 200 and r.json()["by_status"]["Delivered"] == 1
    print("PASS transport: create, status flow, timeline, dashboard")


def test_debt_ledger(client: TestClient, headers: dict) -> int:
    r = client.post(
        "/orders",
        headers=headers,
        json={"client": "Debtor LLC", "amount": "1000000", "currency": "UZS"},
    )
    assert r.status_code == 200, r.text
    order_id = r.json()["id"]
    assert r.json()["currency"] == "UZS"

    r = client.post(
        "/crm/payments",
        headers=headers,
        json={"customer": "Debtor LLC", "amount": 400000, "currency": "UZS", "order_id": order_id},
    )
    assert r.status_code == 200, r.text

    r = client.get("/crm/ledger", headers=headers)
    assert r.status_code == 200, r.text
    row = next(x for x in r.json()["ledger"] if x["customer"] == "Debtor LLC")
    assert row["total_orders"] == 1000000
    assert row["paid_amount"] == 400000
    assert row["outstanding_debt"] == 600000

    r = client.get("/crm/top-debtors", headers=headers)
    assert r.status_code == 200
    assert any(d["customer"] == "Debtor LLC" for d in r.json()["debtors"])
    print("PASS debt ledger: orders, payments, outstanding math, top debtors")
    return order_id


def test_forecast(client: TestClient, headers: dict) -> None:
    db = SessionLocal()
    try:
        material = Material(
            code="PAINT-R", name="Red Paint", unit="kg", quantity=20, min_quantity=5
        )
        db.add(material)
        db.flush()
        db.add(
            MaterialIssue(
                material_id=material.id, quantity=30, reason="production", created_by="admin"
            )
        )
        db.commit()
    finally:
        db.close()

    r = client.get("/warehouse-forecast", headers=headers)
    assert r.status_code == 200, r.text
    item = next(x for x in r.json()["items"] if x["name"] == "Red Paint")
    assert item["consumed_30d"] == 30
    assert item["avg_daily_consumption"] == 1.0
    assert item["days_remaining"] == 20.0
    assert item["low_stock"] is False

    r = client.get("/warehouse-forecast/alerts", headers=headers)
    assert r.status_code == 200
    print("PASS forecast: consumption math, days remaining, alerts endpoint")


def test_kpis(client: TestClient, headers: dict) -> None:
    r = client.get("/dashboard/kpis", headers=headers)
    assert r.status_code == 200, r.text
    kpis = r.json()
    for key in (
        "orders",
        "production_jobs",
        "finished_products",
        "shipped_orders",
        "customers",
        "materials",
        "llp_documents",
        "export_shipments",
    ):
        assert key in kpis, key
    assert kpis["orders"] >= 1
    assert kpis["customers"] >= 1
    assert kpis["materials"] >= 1
    print("PASS dashboard KPIs: all 8 keys present with sane values")


def main() -> None:
    setup_db()
    client = TestClient(app)
    headers = auth_headers(client)

    test_currencies(client, headers)
    test_transport(client, headers)
    test_debt_ledger(client, headers)
    test_forecast(client, headers)
    test_kpis(client, headers)
    print("ALL PHASE 11B SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
