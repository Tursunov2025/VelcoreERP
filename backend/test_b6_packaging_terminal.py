"""B6 Packaging terminal integration test (ephemeral)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.replace(chr(92), '/')}"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-b6-packaging")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    MesBomLine,
    MesJobRouteStep,
    MesProductionJob,
    MesProductionRoute,
    MesProductionStage,
    MesProductCategory,
    MesProductPart,
    MesProductTemplate,
    MesRouteStep,
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


def bootstrap_packaging_job(db: Session) -> int:
    upakovka = (
        db.query(MesProductionStage).filter(MesProductionStage.name == "Upakovka").first()
    )
    sklad = db.query(MesProductionStage).filter(MesProductionStage.name == "Sklad").first()
    assert upakovka and sklad, "Upakovka/Sklad stages missing"

    cat = MesProductCategory(name="Test Cat B6", created_by="admin")
    db.add(cat)
    db.flush()

    part = MesProductPart(
        part_number="PKG-PART-001",
        name="Packaging Test Part",
        unit="dona",
        created_by="admin",
    )
    db.add(part)
    db.flush()

    template = MesProductTemplate(
        category_id=cat.id,
        code="PKG-TPL-B6",
        name="Packaging Test Template",
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
        name="Packaging Route",
        version=1,
        is_default=True,
        is_active=True,
        created_by="admin",
    )
    db.add(route)
    db.flush()
    template.default_route_id = route.id

    db.add(MesRouteStep(route_id=route.id, stage_id=upakovka.id, step_order=0, is_required=True))
    db.add(MesRouteStep(route_id=route.id, stage_id=sklad.id, step_order=1, is_required=True))
    db.commit()

    job = MesProductionJob(
        job_number="JOB-B6-TEST",
        template_id=template.id,
        quantity=1.0,
        status="draft",
        created_by="admin",
    )
    db.add(job)
    db.commit()
    release_job_snapshot(db, job)
    job.status = "released"
    db.commit()
    return job.id


def run_tests() -> None:
    db = setup_db()
    client = TestClient(app)
    token = login(client)
    headers = auth_headers(token)

    admin = db.query(User).filter(User.username == "admin").first()
    set_user_permissions(
        db,
        admin.id,
        {"mes_terminal_packaging": True, "mes_view": True, "mes_jobs_manage": True},
    )
    db.commit()

    r = client.get("/mes/terminal/packaging/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    assert "total_packages_today" in r.json()

    job_id = bootstrap_packaging_job(db)

    r = client.get("/mes/terminal/packaging/queue", headers=headers)
    assert r.status_code == 200, r.text
    assert any(j["id"] == job_id for j in r.json()["jobs"])

    r = client.post(f"/mes/terminal/packaging/jobs/{job_id}/accept", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["step_state"] == "accepted"

    r = client.post(f"/mes/terminal/packaging/jobs/{job_id}/start", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["step_state"] == "in_progress"

    r = client.put(
        f"/mes/terminal/packaging/jobs/{job_id}/packaging-data",
        headers=headers,
        json={
            "package_type": "Karton quti",
            "package_count": 2,
            "net_weight_kg": 10.0,
            "gross_weight_kg": 12.0,
            "notes": "Test packaging",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["package_count"] == 2
    assert len(data["packages"]) == 2
    assert data["packages"][0]["package_number"] == "PACK-JOB-B6-TEST-001"
    assert data["packages"][1]["package_number"] == "PACK-JOB-B6-TEST-002"
    assert data["total_net_weight_kg"] == 10.0
    assert data["total_gross_weight_kg"] == 12.0

    r = client.post(f"/mes/terminal/packaging/jobs/{job_id}/complete", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["step_state"] == "completed"
    assert all(p["status"] == "packed" for p in r.json()["packages"])

    job = load_job(db, job_id)
    active = get_active_step(job)
    assert active is not None
    assert active.stage_name == "Sklad", "Job should move to Warehouse stage"

    r = client.get("/mes/terminal/packaging/dashboard", headers=headers)
    assert r.json()["total_packages_today"] >= 2

    print("ALL B6 PACKAGING TERMINAL TESTS PASSED")
    db.close()
    try:
        os.unlink(TEST_DB)
    except OSError:
        pass


if __name__ == "__main__":
    run_tests()
