"""B7 Finished goods warehouse integration test (ephemeral)."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.replace(chr(92), '/')}"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-b7-warehouse")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    MesBomLine,
    MesJobPackage,
    MesProductionJob,
    MesProductionRoute,
    MesProductionStage,
    MesProductCategory,
    MesProductPart,
    MesProductTemplate,
    MesRouteStep,
    MesWarehouseLocation,
    User,
)
from services.mes_jobs import load_job, release_job_snapshot  # noqa: E402
from services.mes_terminal_common import get_active_step  # noqa: E402
from services.permissions import set_user_permissions  # noqa: E402
from services.seed import seed_defaults  # noqa: E402


def setup_db() -> Session:
    Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    seed_defaults(db)
    return db


def login(client: TestClient) -> str:
    r = client.post("/auth/login", json={"username": "admin", "password": "1234"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def bootstrap_warehouse_job(db: Session) -> tuple[int, list[int], int]:
    sklad = db.query(MesProductionStage).filter(MesProductionStage.name == "Sklad").first()
    yuklash = db.query(MesProductionStage).filter(MesProductionStage.name == "Yuklash").first()
    assert sklad and yuklash

    cat = MesProductCategory(name="Test Cat B7", created_by="admin")
    db.add(cat)
    db.flush()

    part = MesProductPart(
        part_number="WH-PART-001",
        name="Warehouse Test Part",
        unit="dona",
        created_by="admin",
    )
    db.add(part)
    db.flush()

    template = MesProductTemplate(
        category_id=cat.id,
        code="WH-TPL-B7",
        name="Warehouse Test Product",
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
        name="Warehouse Route",
        version=1,
        is_default=True,
        is_active=True,
        created_by="admin",
    )
    db.add(route)
    db.flush()
    template.default_route_id = route.id

    db.add(MesRouteStep(route_id=route.id, stage_id=sklad.id, step_order=0, is_required=True))
    db.add(MesRouteStep(route_id=route.id, stage_id=yuklash.id, step_order=1, is_required=True))
    db.commit()

    job = MesProductionJob(
        job_number="JOB-B7-TEST",
        template_id=template.id,
        quantity=1.0,
        status="draft",
        created_by="admin",
    )
    db.add(job)
    db.commit()
    release_job_snapshot(db, job)
    job.status = "released"
    db.flush()

    pkg1 = MesJobPackage(
        job_id=job.id,
        package_number="PACK-JOB-B7-TEST-001",
        package_type="Karton",
        net_weight_kg=5.0,
        gross_weight_kg=6.0,
        status="packed",
    )
    pkg2 = MesJobPackage(
        job_id=job.id,
        package_number="PACK-JOB-B7-TEST-002",
        package_type="Karton",
        net_weight_kg=5.0,
        gross_weight_kg=6.0,
        status="packed",
    )
    db.add(pkg1)
    db.add(pkg2)
    db.commit()

    loc = db.query(MesWarehouseLocation).filter(MesWarehouseLocation.code == "A-01-01").first()
    assert loc, "Default location A-01-01 missing"

    return job.id, [pkg1.id, pkg2.id], loc.id


def run_tests() -> None:
    db = setup_db()
    client = TestClient(app)
    token = login(client)
    headers = auth_headers(token)

    admin = db.query(User).filter(User.username == "admin").first()
    set_user_permissions(
        db,
        admin.id,
        {"mes_terminal_warehouse": True, "mes_edit": True, "mes_view": True},
    )
    db.commit()

    r = client.get("/mes/terminal/warehouse/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    assert "inventory_items" in r.json()

    r = client.get("/mes/terminal/warehouse/locations", headers=headers)
    assert r.status_code == 200, r.text
    assert any(loc["code"] == "A-01-01" for loc in r.json()["locations"])

    job_id, package_ids, location_id = bootstrap_warehouse_job(db)

    r = client.get("/mes/terminal/warehouse/queue", headers=headers)
    assert r.status_code == 200, r.text
    assert any(j["id"] == job_id for j in r.json()["jobs"])

    r = client.post(f"/mes/terminal/warehouse/jobs/{job_id}/accept", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["step_state"] == "accepted"

    r = client.post(f"/mes/terminal/warehouse/jobs/{job_id}/start", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["step_state"] == "in_progress"

    for pkg_id in package_ids:
        r = client.post(
            f"/mes/terminal/warehouse/jobs/{job_id}/packages/{pkg_id}/place",
            headers=headers,
            json={"location_id": location_id},
        )
        assert r.status_code == 200, r.text

    r = client.get("/mes/terminal/warehouse/inventory", headers=headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) >= 1
    item = r.json()["items"][0]
    assert item["product_code"] == "WH-TPL-B7"
    assert "A-01-01" in item["locations"]

    r = client.post(f"/mes/terminal/warehouse/jobs/{job_id}/complete", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["step_state"] == "completed"

    job = load_job(db, job_id)
    active = get_active_step(job)
    assert active is not None
    assert active.stage_name == "Yuklash", "Job should move to Dispatch stage"

    r = client.post(
        "/mes/warehouse/locations",
        headers=headers,
        json={"code": "C-02-01", "description": "Test zone"},
    )
    assert r.status_code == 200, r.text

    print("ALL B7 WAREHOUSE TERMINAL TESTS PASSED")
    db.close()
    try:
        os.unlink(TEST_DB)
    except OSError:
        pass


if __name__ == "__main__":
    run_tests()
