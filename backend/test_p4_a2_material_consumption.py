"""P4-A2 Material consumption planning integration test (ephemeral)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.replace(chr(92), '/')}"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-p4-a2-consumption")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    Material,
    MesBomLine,
    MesProductionJob,
    MesProductionRoute,
    MesProductionStage,
    MesProductCategory,
    MesProductPart,
    MesProductTemplate,
    MesRouteStep,
    User,
)
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


def bootstrap_job(db: Session) -> tuple[int, int, int]:
    lazer = db.query(MesProductionStage).filter(MesProductionStage.name == "Lazer").first()
    assert lazer

    sheet = db.query(Material).filter(Material.code == "MAT-TEMIR").first()
    paint = db.query(Material).filter(Material.code == "MAT-BOYOQ").first()
    assert sheet and paint

    part = MesProductPart(
        part_number="POLKA-1000",
        name="Polka 1000",
        unit="dona",
        created_by="admin",
    )
    db.add(part)
    db.flush()

    cat = MesProductCategory(name="P4A2 Cat", created_by="admin")
    db.add(cat)
    db.flush()

    template = MesProductTemplate(
        category_id=cat.id,
        code="TPL-P4A2",
        name="P4A2 Product",
        created_by="admin",
    )
    db.add(template)
    db.flush()

    db.add(
        MesBomLine(
            template_id=template.id,
            part_id=part.id,
            required_quantity=1.0,
            sort_order=0,
            is_active=True,
        )
    )

    route = MesProductionRoute(
        template_id=template.id,
        name="P4A2 Route",
        version=1,
        is_default=True,
        is_active=True,
        created_by="admin",
    )
    db.add(route)
    db.flush()
    template.default_route_id = route.id

    db.add(
        MesRouteStep(
            route_id=route.id,
            stage_id=lazer.id,
            step_order=0,
            is_required=True,
        )
    )

    job = MesProductionJob(
        job_number="JOB-P4A2-001",
        template_id=template.id,
        quantity=10.0,
        status="draft",
        created_by="admin",
    )
    db.add(job)
    db.commit()

    return part.id, job.id, sheet.id


def test_p4_a2_material_consumption():
    db = setup_db()
    client = TestClient(app)

    admin = db.query(User).filter(User.username == "admin").first()
    set_user_permissions(
        db,
        admin.id,
        {"materials_view": True, "materials_edit": True, "mes_jobs_manage": True, "mes_view": True},
    )
    db.commit()

    token = login(client)
    headers = auth_headers(token)

    part_id, job_id, sheet_id = bootstrap_job(db)
    paint = db.query(Material).filter(Material.code == "MAT-BOYOQ").first()
    sheet_before = db.query(Material).filter(Material.id == sheet_id).first()
    stock_before = float(sheet_before.quantity)

    # Attach materials to part (Material BOM editor)
    r1 = client.post(
        f"/materials/parts/{part_id}/bom",
        headers=headers,
        json={"material_id": sheet_id, "quantity_per_part": 2.4},
    )
    assert r1.status_code == 200, r1.text
    r2 = client.post(
        f"/materials/parts/{part_id}/bom",
        headers=headers,
        json={"material_id": paint.id, "quantity_per_part": 0.12},
    )
    assert r2.status_code == 200, r2.text

    bom = client.get(f"/materials/parts/{part_id}/bom", headers=headers)
    assert bom.status_code == 200
    assert len(bom.json()["lines"]) == 2

    # Release job -> material reservations
    release = client.post(f"/mes/jobs/{job_id}/release", headers=headers)
    assert release.status_code == 200, release.text

    reservations = client.get(f"/materials/jobs/{job_id}/reservations", headers=headers)
    assert reservations.status_code == 200
    res_map = {r["material_id"]: r for r in reservations.json()["reservations"]}

    assert sheet_id in res_map
    assert paint.id in res_map
    assert res_map[sheet_id]["required_quantity"] == 24.0  # 10 parts * 2.4 kg
    assert res_map[paint.id]["required_quantity"] == 1.2  # 10 * 0.12 kg
    assert res_map[sheet_id]["reserved_quantity"] == 24.0
    assert res_map[paint.id]["reserved_quantity"] == 1.2

    # Stock NOT deducted
    db.refresh(sheet_before)
    assert float(sheet_before.quantity) == stock_before

    # Shortages dashboard
    planning = client.get("/materials/planning/shortages", headers=headers)
    assert planning.status_code == 200
    payload = planning.json()
    assert "shortages" in payload
    sheet_row = next(s for s in payload["shortages"] if s["material_id"] == sheet_id)
    assert sheet_row["required_quantity"] == 24.0
    assert sheet_row["available_quantity"] == stock_before
    assert sheet_row["shortage_quantity"] == 0.0

    # Dashboard includes shortage count
    dash = client.get("/materials/dashboard", headers=headers)
    assert dash.status_code == 200
    assert "shortage_count" in dash.json()

    # View-only cannot edit BOM
    kraska = db.query(User).filter(User.username == "kraska1").first()
    set_user_permissions(db, kraska.id, {"materials_view": True, "materials_edit": False})
    db.commit()
    view_token = login(client, "kraska1", "1111")
    view_headers = auth_headers(view_token)
    denied = client.post(
        f"/materials/parts/{part_id}/bom",
        headers=view_headers,
        json={"material_id": sheet_id, "quantity_per_part": 1},
    )
    assert denied.status_code == 403

    db.close()
    print("P4-A2 material consumption planning: ALL TESTS PASSED")


if __name__ == "__main__":
    test_p4_a2_material_consumption()
