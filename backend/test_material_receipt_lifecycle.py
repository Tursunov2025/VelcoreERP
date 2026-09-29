"""Disposable acceptance for professional material receipt documents."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB.replace(chr(92), '/')}",
    "DB_PATH": TEST_DB,
    "DATABASE_GUARD": "false",
    "ENVIRONMENT": "test",
    "JWT_SECRET_KEY": "material-receipt-lifecycle-secret",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import AuditLog, Material, MaterialReceipt, MaterialStockLengthLot, MaterialStockMovement  # noqa: E402
from services.seed import seed_defaults  # noqa: E402


def ok(response, status=200):
    assert response.status_code == status, (response.status_code, response.text)
    return response.json()


def test_material_receipt_document_lifecycle():
    Base.metadata.create_all(engine)
    run_migrations(); run_migrations()
    db = SessionLocal(); seed_defaults(db)
    client = TestClient(app)
    token = ok(client.post("/auth/login", json={"username": "admin", "password": "1234"}))["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    metal = next(row for row in ok(client.get("/materials/categories", headers=headers))["categories"] if row["code"] == "METAL")
    material = ok(client.post("/materials/items", headers=headers, json={
        "code": "PR-RT-40X20X1.5", "name": "Receipt lifecycle profile",
        "category_id": metal["id"], "material_type": "PROFILE", "profile_type": "RECTANGULAR",
        "unit": "m", "purchase_unit": "pcs", "width_mm": 40, "height_mm": 20,
        "thickness_mm": 1.5, "steel_grade": "St37", "current_stock": 0,
    }))
    mid = material["id"]
    rows = [
        {"length_m": 8, "piece_count": 20, "unit_cost": 12000, "price_basis": "PER_METER", "warehouse_name": "TEST Raw", "location_code": "A-01", "lot_number": "HEAT-8"},
        {"length_m": 10, "piece_count": 15, "unit_cost": 12000, "price_basis": "PER_METER", "warehouse_name": "TEST Raw", "location_code": "A-02", "lot_number": "HEAT-10"},
        {"length_m": 12, "piece_count": 10, "unit_cost": 12000, "price_basis": "PER_METER", "warehouse_name": "TEST Raw", "location_code": "A-03", "lot_number": "HEAT-12"},
    ]
    draft_body = {
        "material_id": mid, "receipt_number": "TEST-RCP-001", "received_at": "2026-09-04T09:00:00",
        "supplier_name": "TEST Supplier", "supplier_invoice": "TEST-INV-001",
        "reference": "TEST-INV-001", "warehouse_name": "TEST Raw", "price_basis": "PER_METER",
        "currency": "UZS", "notes": "Disposable receipt", "profile_rows": rows,
        "operation_key": "receipt-create-test-001", "confirm": False,
    }
    draft = ok(client.post("/materials/receipts", headers=headers, json=draft_body))
    assert draft["status"] == "DRAFT" and draft["quantity"] == 430
    assert draft["total_pieces"] == 45 and draft["stock_applied"] is False
    assert ok(client.get(f"/materials/items/{mid}", headers=headers))["current_stock"] == 0
    retry_create = ok(client.post("/materials/receipts", headers=headers, json=draft_body))
    assert retry_create["id"] == draft["id"] and retry_create["idempotent"] is True
    edited_body = {**draft_body, "supplier_name": "TEST Supplier Updated", "expected_version": draft["version"]}
    edited = ok(client.put(f"/materials/receipts/{draft['id']}", headers=headers, json=edited_body))
    assert edited["supplier_name"] == "TEST Supplier Updated" and edited["version"] == 2
    assert ok(client.get(f"/materials/items/{mid}", headers=headers))["current_stock"] == 0
    stale = client.put(f"/materials/receipts/{draft['id']}", headers=headers, json=edited_body)
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "material_receipt_version_conflict"

    confirm_body = {"operation_key": "receipt-confirm-test-001"}
    confirmed = ok(client.post(f"/materials/receipts/{draft['id']}/confirm", headers=headers, json=confirm_body))
    assert confirmed["status"] == "CONFIRMED" and confirmed["material"]["current_stock"] == 430
    assert [(r["length_m"], r["pieces_on_hand"], r["total_meters"]) for r in confirmed["length_lots"]] == [
        (8.0, 20, 160.0), (10.0, 15, 150.0), (12.0, 10, 120.0),
    ]
    assert all(row["receipt_document_id"] == draft["id"] for row in confirmed["length_lots"])
    assert all(row["receipt_id"] is None for row in confirmed["length_lots"])
    reloaded = ok(client.get(f"/materials/receipts/{draft['id']}", headers=headers))
    assert reloaded["total_pieces"] == 45 and len(reloaded["length_lots"]) == 3
    retry_confirm = ok(client.post(f"/materials/receipts/{draft['id']}/confirm", headers=headers, json=confirm_body))
    assert retry_confirm["idempotent"] is True
    assert db.query(MaterialStockMovement).filter_by(reference_type="receipt", reference_id=draft["id"], movement_type="receipt").count() == 1
    assert db.query(MaterialStockLengthLot).filter_by(receipt_document_id=draft["id"]).count() == 3

    reverse_body = {"operation_key": "receipt-reverse-test-001", "reason": "Disposable correction"}
    reversed_doc = ok(client.post(f"/materials/receipts/{draft['id']}/reverse", headers=headers, json=reverse_body))
    assert reversed_doc["status"] == "REVERSED" and reversed_doc["material"]["current_stock"] == 0
    assert all(row["pieces_on_hand"] == 0 and row["total_meters"] == 0 for row in reversed_doc["length_lots"])
    retry_reverse = ok(client.post(f"/materials/receipts/{draft['id']}/reverse", headers=headers, json=reverse_body))
    assert retry_reverse["idempotent"] is True
    assert db.query(MaterialStockMovement).filter_by(reference_type="receipt", reference_id=draft["id"], movement_type="receipt_reversal").count() == 1

    corrected = ok(client.post("/materials/receipts", headers=headers, json={
        "material_id": mid, "receipt_number": "TEST-RCP-002", "supplier_name": "TEST Supplier",
        "warehouse_name": "TEST Raw", "profile_rows": [{
            "length_m": 10, "piece_count": 14, "unit_cost": 120000,
            "price_basis": "PER_PIECE", "warehouse_name": "TEST Raw",
            "location_code": "A-02", "lot_number": "HEAT-10-CORRECTED",
        }], "operation_key": "receipt-create-test-002", "confirm": True,
    }))
    assert corrected["status"] == "CONFIRMED" and corrected["quantity"] == 140
    assert corrected["length_lots"][0]["pieces_on_hand"] == 14
    assert corrected["length_lots"][0]["unit_cost"] == 12000
    corrected_lot = db.query(MaterialStockLengthLot).filter_by(receipt_document_id=corrected["id"]).one()
    corrected_lot.pieces_reserved = 1; db.commit()
    blocked = client.post(f"/materials/receipts/{corrected['id']}/reverse", headers=headers, json={
        "operation_key": "receipt-reverse-test-002", "reason": "Must be blocked",
    })
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "material_receipt_reversal_reserved"
    assert db.query(Material).filter_by(id=mid).one().quantity == 140

    corrected_lot.pieces_reserved = 0
    corrected_lot.pieces_on_hand = 13
    corrected_lot.total_meters = 130
    db.query(Material).filter_by(id=mid).one().quantity = 130
    db.commit()
    consumed_blocked = client.post(f"/materials/receipts/{corrected['id']}/reverse", headers=headers, json={
        "operation_key": "receipt-reverse-test-003", "reason": "Consumed stock must be blocked",
    })
    assert consumed_blocked.status_code == 409
    assert consumed_blocked.json()["detail"]["code"] == "material_receipt_reversal_consumed"
    db.refresh(corrected_lot)
    assert corrected_lot.pieces_on_hand == 13 and corrected_lot.total_meters == 130
    assert db.query(Material).filter_by(id=mid).one().quantity == 130

    missing_location = client.post("/materials/receipts", headers=headers, json={
        "material_id": mid, "profile_rows": [{"length_m": 6, "piece_count": 1, "warehouse_name": "TEST Raw"}],
        "operation_key": "receipt-invalid-location", "confirm": False,
    })
    assert missing_location.status_code == 400
    assert missing_location.json()["detail"]["code"] == "material_receipt_location_required"
    assert db.query(AuditLog).filter_by(entity_type="material_receipt", entity_id=draft["id"]).count() >= 3
    assert db.query(MaterialReceipt).filter_by(id=draft["id"]).one().status == "REVERSED"
    db.close()
    print("Professional material receipt lifecycle: ALL TESTS PASSED (45 pcs / 430 m / idempotent reversal)")


if __name__ == "__main__":
    test_material_receipt_document_lifecycle()
