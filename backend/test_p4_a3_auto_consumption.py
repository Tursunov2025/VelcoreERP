"""P4-A3 Automatic material consumption integration test (ephemeral)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.replace(chr(92), '/')}"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-p4-a3-auto-consume")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    Material,
    MaterialConsumption,
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
from services.mes_jobs import release_job_snapshot  # noqa: E402
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


def bootstrap_lazer_job(db: Session) -> tuple[int, int, int, int]:
    lazer = db.query(MesProductionStage).filter(MesProductionStage.name == "Lazer").first()
    assert lazer

    sheet = db.query(Material).filter(Material.code == "MAT-TEMIR").first()
    paint = db.query(Material).filter(Material.code == "MAT-BOYOQ").first()
    assert sheet and paint
    sheet_qty_before = float(sheet.quantity)
    paint_qty_before = float(paint.quantity)

    part = MesProductPart(
        part_number="POLKA-P4A3",
        name="Polka P4A3",
        unit="dona",
        created_by="admin",
    )
    db.add(part)
    db.flush()

    cat = MesProductCategory(name="P4A3 Cat", created_by="admin")
    db.add(cat)
    db.flush()

    template = MesProductTemplate(
        category_id=cat.id,
        code="TPL-P4A3",
        name="P4A3 Product",
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
        name="P4A3 Lazer Route",
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
        job_number="JOB-P4A3-001",
        template_id=template.id,
        quantity=10.0,
        status="draft",
        created_by="admin",
    )
    db.add(job)
    db.commit()

    return part.id, job.id, sheet.id, paint.id


def test_p4_a3_automatic_material_consumption():
    db = setup_db()
    client = TestClient(app)

    admin = db.query(User).filter(User.username == "admin").first()
    set_user_permissions(
        db,
        admin.id,
        {
            "materials_view": True,
            "materials_edit": True,
            "mes_terminal_lazer": True,
            "mes_terminal_kraska": True,
            "mes_jobs_manage": True,
            "mes_view": True,
        },
    )
    db.commit()

    token = login(client)
    headers = auth_headers(token)

    part_id, job_id, sheet_id, paint_id = bootstrap_lazer_job(db)
    sheet = db.query(Material).filter(Material.id == sheet_id).first()
    paint = db.query(Material).filter(Material.id == paint_id).first()
    sheet_before = float(sheet.quantity)
    paint_before = float(paint.quantity)

    # Consumption rules seeded (METAL→Lazer, PAINT→Kraska)
    rules = client.get("/materials/consumption-rules", headers=headers)
    assert rules.status_code == 200
    assert any(r["material_id"] == sheet_id and r["consuming_stage"] == "Lazer" for r in rules.json()["rules"])

    # Part material BOM
    client.post(
        f"/materials/parts/{part_id}/bom",
        headers=headers,
        json={"material_id": sheet_id, "quantity_per_part": 2.4},
    )
    client.post(
        f"/materials/parts/{part_id}/bom",
        headers=headers,
        json={"material_id": paint_id, "quantity_per_part": 0.12},
    )

    # Release job
    release = client.post(f"/mes/jobs/{job_id}/release", headers=headers)
    assert release.status_code == 200, release.text

    # Accept + start Lazer → auto consume metal only
    client.post(f"/mes/terminal/lazer/jobs/{job_id}/accept", headers=headers)
    start = client.post(f"/mes/terminal/lazer/jobs/{job_id}/start", headers=headers)
    assert start.status_code == 200, start.text

    db.refresh(sheet)
    db.refresh(paint)
    assert float(sheet.quantity) == sheet_before - 24.0  # 10 * 2.4
    assert float(paint.quantity) == paint_before  # paint not consumed at Lazer

    consumptions = client.get(f"/materials/jobs/{job_id}/consumptions", headers=headers)
    assert consumptions.status_code == 200
    cons = consumptions.json()["consumptions"]
    assert len(cons) == 1
    assert cons[0]["material_id"] == sheet_id
    assert cons[0]["stage"] == "Lazer"
    assert cons[0]["quantity"] == 24.0
    assert cons[0]["movement_id"] is not None

    # Job material cost
    cost = client.get(f"/materials/jobs/{job_id}/material-cost", headers=headers)
    assert cost.status_code == 200
    assert cost.json()["total_cost"] > 0
    assert "Lazer" in cost.json()["by_stage"]

    # Dashboard consumed today
    dash = client.get("/materials/dashboard", headers=headers)
    assert dash.status_code == 200
    assert dash.json()["consumed_today"] >= 1

    # Insufficient stock blocks Lazer start on another job
    sheet.quantity = 1.0
    db.commit()

    template_id = db.query(MesProductionJob).filter(MesProductionJob.id == job_id).first().template_id
    job2 = MesProductionJob(
        job_number="JOB-P4A3-002",
        template_id=template_id,
        quantity=10.0,
        status="draft",
        created_by="admin",
    )
    db.add(job2)
    db.commit()

    assert client.post(f"/mes/jobs/{job2.id}/release", headers=headers).status_code == 200
    client.post(f"/mes/terminal/lazer/jobs/{job2.id}/accept", headers=headers)
    blocked = client.post(f"/mes/terminal/lazer/jobs/{job2.id}/start", headers=headers)
    assert blocked.status_code == 400
    assert "Insufficient stock" in blocked.json()["detail"]

    db.close()
    print("P4-A3 automatic material consumption: ALL TESTS PASSED")


if __name__ == "__main__":
    test_p4_a3_automatic_material_consumption()
