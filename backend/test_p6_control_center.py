"""P6 Executive Control Center integration test (ephemeral)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.replace(chr(92), '/')}"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-p6-control-center")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from services.seed import seed_defaults  # noqa: E402


def setup():
    Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    seed_defaults(db)
    db.close()


def login(client: TestClient) -> dict:
    r = client.post("/auth/login", json={"username": "admin", "password": "1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_p6_control_center():
    setup()
    client = TestClient(app)
    h = login(client)

    exec_get = client.get("/admin/settings/executive", headers=h)
    assert exec_get.status_code == 200, exec_get.text
    assert "nav_visibility_json" in exec_get.json()

    exec_put = client.put(
        "/admin/settings/executive",
        headers=h,
        json={
            "nav_visibility_json": '{"orders": true, "mes": true}',
            "dashboard_widgets_json": '[{"id":"clock","enabled":true,"order":1}]',
            "mobile_app_json": '{"latest_version":"1.0.1","force_update":false}',
        },
    )
    assert exec_put.status_code == 200, exec_put.text

    ui = client.get("/control-center/config/ui", headers=h)
    assert ui.status_code == 200, ui.text
    body = ui.json()
    assert "nav_visibility" in body
    assert "dashboard_widgets" in body
    assert body["mobile_app"] is not None

    orders = client.get("/control-center/orders", headers=h)
    assert orders.status_code == 200, orders.text
    assert "items" in orders.json()
    assert "summary" in orders.json()

    csv_export = client.get("/control-center/orders/export.csv", headers=h)
    assert csv_export.status_code == 200, csv_export.text
    assert "Reference" in csv_export.text

    logs = client.get("/admin/audit-logs?limit=10&action=update", headers=h)
    assert logs.status_code == 200, logs.text

    denied = client.get("/control-center/orders")
    assert denied.status_code == 401

    print("P6 control center: ALL TESTS PASSED")


if __name__ == "__main__":
    test_p6_control_center()
