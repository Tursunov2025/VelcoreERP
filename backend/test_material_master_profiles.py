"""Focused disposable acceptance for professional material master and length lots."""

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
    "JWT_SECRET_KEY": "material-master-test-secret",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, inspect, text  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import AuditLog, Material, MaterialBomLine, MaterialReceipt, MaterialStockLengthLot, MesProductPart  # noqa: E402
from services.seed import seed_defaults  # noqa: E402
from migrations.material_master import upgrade as upgrade_material_master  # noqa: E402


def ok(response, status=200):
    assert response.status_code == status, (response.status_code, response.text)
    return response.json()


def test_professional_material_master_and_profile_lots():
    legacy_path = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    legacy_engine = create_engine(f"sqlite:///{legacy_path.replace(chr(92), '/')}")
    with legacy_engine.begin() as connection:
        connection.execute(text("CREATE TABLE materials (id INTEGER PRIMARY KEY, code VARCHAR, name VARCHAR NOT NULL, unit VARCHAR DEFAULT 'dona', quantity FLOAT DEFAULT 0, min_quantity FLOAT DEFAULT 5, unit_cost FLOAT DEFAULT 0, is_active BOOLEAN DEFAULT 1)"))
        connection.execute(text("CREATE TABLE material_receipts (id INTEGER PRIMARY KEY, material_id INTEGER NOT NULL, quantity FLOAT NOT NULL)"))
        connection.execute(text("INSERT INTO materials (id, code, name, unit, quantity) VALUES (1, 'LEGACY-PAINT', 'Legacy paint', 'l', 7)"))
    upgrade_material_master(legacy_engine); upgrade_material_master(legacy_engine)
    with legacy_engine.connect() as connection:
        row = connection.execute(text("SELECT code, name, quantity, material_type FROM materials WHERE id=1")).one()
        assert tuple(row) == ("LEGACY-PAINT", "Legacy paint", 7.0, "CONSUMABLE")
    assert "material_stock_length_lots" in inspect(legacy_engine).get_table_names()
    legacy_engine.dispose()

    Base.metadata.create_all(engine)
    run_migrations(); run_migrations()
    db = SessionLocal(); seed_defaults(db)
    client = TestClient(app)
    token = ok(client.post("/auth/login", json={"username": "admin", "password": "1234"}))["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    metal = next(row for row in ok(client.get("/materials/categories", headers=headers))["categories"] if row["code"] == "METAL")

    square = ok(client.post("/materials/items", headers=headers, json={
        "code": "", "auto_code": True, "name": "Square profile 20x20x1",
        "category_id": metal["id"], "material_type": "PROFILE", "profile_type": "SQUARE",
        "unit": "m", "purchase_unit": "pcs", "width_mm": 20, "height_mm": 20,
        "thickness_mm": 1, "steel_grade": "St37", "minimum_stock": 20,
    }))
    assert square["code"] == "PR-SQ-20X20X1"
    assert square["theoretical_weight_kg_per_m"] > 0
    square_receipt = ok(client.post("/materials/receipts", headers=headers, json={
        "material_id": square["id"], "length_m": 6, "piece_count": 2,
        "quantity": 12, "reference": "TEST-SQ-6", "location_code": "A-04",
    }))
    assert square_receipt["length_lot"]["total_meters"] == 12
    bad_conversion = client.post("/materials/receipts", headers=headers, json={
        "material_id": square["id"], "length_m": 6, "piece_count": 2, "quantity": 11,
    })
    assert bad_conversion.status_code == 400
    assert bad_conversion.json()["detail"]["code"] == "material_conversion_invalid"
    square_updated = ok(client.put(f"/materials/items/{square['id']}", headers=headers, json={
        "material_type": "PROFILE", "profile_type": "SQUARE", "unit": "m", "purchase_unit": "pcs",
        "width_mm": 20, "height_mm": 20, "thickness_mm": 1, "steel_grade": "St37",
        "new_length_lots": [{"length_m": 8, "piece_count": 1, "location_code": "A-05"}],
    }))
    assert square_updated["current_stock"] == 20
    assert square_updated["length_lot_summary"]["lengths_m"] == [6.0, 8.0]

    lots = [
        {"length_m": 8, "piece_count": 20, "warehouse_name": "TEST Raw", "location_code": "A-01", "lot_number": "LOT-8"},
        {"length_m": 10, "piece_count": 15, "warehouse_name": "TEST Raw", "location_code": "A-02", "lot_number": "LOT-10"},
        {"length_m": 12, "piece_count": 10, "warehouse_name": "TEST Raw", "location_code": "A-03", "lot_number": "LOT-12"},
    ]
    rectangular = ok(client.post("/materials/items", headers=headers, json={
        "code": "", "auto_code": True, "name": "Rectangular profile 40x20x1.5",
        "category_id": metal["id"], "material_type": "PROFILE", "profile_type": "RECTANGULAR",
        "unit": "m", "purchase_unit": "pcs", "width_mm": 40, "height_mm": 20,
        "thickness_mm": 1.5, "steel_grade": "St37", "unit_cost": 12500,
        "initial_length_lots": lots,
    }))
    assert rectangular["code"] == "PR-RT-40X20X1.5"
    assert rectangular["current_stock"] == 430
    assert rectangular["length_lot_summary"] == {"total_pieces": 45, "total_meters": 430.0, "lengths_m": [8.0, 10.0, 12.0]}

    reloaded = ok(client.get(f"/materials/items/{rectangular['id']}", headers=headers))
    assert [(row["length_m"], row["pieces_on_hand"], row["total_meters"]) for row in reloaded["length_lots"]] == [
        (8.0, 20, 160.0), (10.0, 15, 150.0), (12.0, 10, 120.0),
    ]
    assert len({row["material_id"] for row in reloaded["length_lots"]}) == 1

    duplicate = client.post("/materials/items", headers=headers, json={
        "code": "PR-RT-40X20X1.5", "name": "Duplicate profile", "category_id": metal["id"],
        "material_type": "PROFILE", "profile_type": "RECTANGULAR", "unit": "m",
        "purchase_unit": "pcs", "width_mm": 40, "height_mm": 20, "thickness_mm": 1.5,
    })
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"]["code"] == "material_code_exists"

    sheet = ok(client.post("/materials/items", headers=headers, json={
        "code": "SH-ST37-1250X2500X2", "name": "Sheet St37 2 mm", "category_id": metal["id"],
        "material_type": "SHEET_METAL", "unit": "pcs", "purchase_unit": "pcs",
        "width_mm": 1250, "length_mm": 2500, "thickness_mm": 2,
        "steel_grade": "St37", "current_stock": 12,
    }))
    assert sheet["sheet_area_m2"] == 3.125 and abs(sheet["sheet_weight_kg"] - 49.0625) < 0.001
    assert sheet["current_stock"] == 12

    part = MesProductPart(part_number="TEST-PROFILE-PART", name="Profile detail", unit="dona", created_by="test")
    db.add(part); db.commit(); db.refresh(part)
    bom = ok(client.post(f"/materials/parts/{part.id}/bom", headers=headers, json={
        "material_id": rectangular["id"], "quantity_per_part": 2.35,
    }))
    assert bom["material_id"] == rectangular["id"] and bom["quantity_per_part"] == 2.35
    assert db.query(Material).filter_by(code="PR-RT-40X20X1.5").count() == 1
    assert db.query(MaterialBomLine).filter_by(material_id=rectangular["id"]).count() == 1
    assert db.query(MaterialStockLengthLot).filter_by(material_id=rectangular["id"]).count() == 3
    assert db.query(MaterialReceipt).filter_by(material_id=rectangular["id"]).count() == 3
    assert db.query(AuditLog).filter_by(entity_type="material_stock_length_lot").count() == 5

    db.close()
    print("Professional material master: ALL TESTS PASSED (45 pcs / 430 m / BOM 2.35 m)")


if __name__ == "__main__":
    test_professional_material_master_and_profile_lots()
