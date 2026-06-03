"""P4-A1 Raw materials warehouse integration test (ephemeral)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.replace(chr(92), '/')}"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-p4-a1-materials")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import Material, MaterialCategory, User  # noqa: E402
from services.permissions import set_user_permissions  # noqa: E402
from services.seed import seed_defaults  # noqa: E402


def setup_db() -> Session:
    Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    seed_defaults(db)
    return db


def login(client: TestClient, username: str = "admin", password: str = "1234") -> str:
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_p4_a1_materials_warehouse():
    db = setup_db()
    client = TestClient(app)

    # Operator without permissions should be denied
    kesish = db.query(User).filter(User.username == "kesish1").first()
    set_user_permissions(db, kesish.id, {"materials_view": False, "materials_edit": False})
    db.commit()
    op_token = login(client, "kesish1", "1111")
    denied = client.get("/materials/dashboard", headers=auth_headers(op_token))
    assert denied.status_code == 403

    ombor = db.query(User).filter(User.username == "ombor1").first()
    set_user_permissions(
        db,
        ombor.id,
        {"materials_view": True, "materials_edit": True},
    )
    db.commit()
    wh_token = login(client, "ombor1", "1111")
    headers = auth_headers(wh_token)

    # Dashboard
    dash = client.get("/materials/dashboard", headers=headers)
    assert dash.status_code == 200, dash.text
    stats = dash.json()
    assert "low_stock" in stats
    assert "receipts_today" in stats
    assert "issues_today" in stats
    assert "inventory_value" in stats
    assert stats["inventory_value"] > 0

    # Categories seeded
    cats = client.get("/materials/categories", headers=headers)
    assert cats.status_code == 200
    category_list = cats.json()["categories"]
    assert len(category_list) >= 3
    metal = next(c for c in category_list if c["code"] == "METAL")

    # Materials list
    items = client.get("/materials/items", headers=headers)
    assert items.status_code == 200
    materials = items.json()["materials"]
    assert len(materials) >= 3
    temir = next(m for m in materials if m["code"] == "MAT-TEMIR")
    assert temir["current_stock"] == 100
    assert temir["minimum_stock"] == 20
    assert temir["category_id"] == metal["id"]

    # Create material
    created = client.post(
        "/materials/items",
        headers=headers,
        json={
            "code": "MAT-BOLT",
            "name": "Bolt M8",
            "unit": "dona",
            "category_id": metal["id"],
            "minimum_stock": 50,
            "current_stock": 100,
            "unit_cost": 500,
        },
    )
    assert created.status_code == 200, created.text
    mat_id = created.json()["id"]

    # Receipt
    receipt = client.post(
        "/materials/receipts",
        headers=headers,
        json={
            "material_id": mat_id,
            "quantity": 25,
            "unit_cost": 550,
            "reference": "INV-001",
            "notes": "Test receipt",
        },
    )
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["material"]["current_stock"] == 125

    # Issue
    issue = client.post(
        "/materials/issues",
        headers=headers,
        json={
            "material_id": mat_id,
            "quantity": 10,
            "reason": "Production",
            "notes": "Test issue",
        },
    )
    assert issue.status_code == 200, issue.text
    assert issue.json()["material"]["current_stock"] == 115

    # Adjustment
    adj = client.post(
        "/materials/adjustments",
        headers=headers,
        json={
            "material_id": mat_id,
            "quantity_after": 110,
            "reason": "Inventory count",
        },
    )
    assert adj.status_code == 200, adj.text
    assert adj.json()["material"]["current_stock"] == 110

    # Movements ledger
    moves = client.get("/materials/movements", headers=headers)
    assert moves.status_code == 200
    movement_types = {m["movement_type"] for m in moves.json()["movements"]}
    assert "receipt" in movement_types
    assert "issue" in movement_types
    assert "adjustment" in movement_types

    # View-only cannot edit
    kraska = db.query(User).filter(User.username == "kraska1").first()
    set_user_permissions(db, kraska.id, {"materials_view": True, "materials_edit": False})
    db.commit()
    view_token = login(client, "kraska1", "1111")
    view_headers = auth_headers(view_token)
    can_view = client.get("/materials/items", headers=view_headers)
    assert can_view.status_code == 200
    cannot_edit = client.post(
        "/materials/receipts",
        headers=view_headers,
        json={"material_id": mat_id, "quantity": 1},
    )
    assert cannot_edit.status_code == 403

    # Insufficient stock
    bad_issue = client.post(
        "/materials/issues",
        headers=headers,
        json={"material_id": mat_id, "quantity": 9999},
    )
    assert bad_issue.status_code == 400

    db.close()
    print("P4-A1 materials warehouse: ALL TESTS PASSED")


if __name__ == "__main__":
    test_p4_a1_materials_warehouse()
