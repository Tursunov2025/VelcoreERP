"""B5 QC terminal integration test (ephemeral)."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Use isolated DB for test
TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.replace(chr(92), '/')}"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-b5-qc-terminal")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from database import SessionLocal, Base, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    MesJobBomLine,
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
from services.mes_jobs import release_job_snapshot  # noqa: E402
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


def bootstrap_qc_job(db: Session) -> int:
    nazorat = (
        db.query(MesProductionStage).filter(MesProductionStage.name == "Nazorat").first()
    )
    assert nazorat, "Nazorat stage missing"

    cat = MesProductCategory(name="Test Cat B5", created_by="admin")
    db.add(cat)
    db.flush()

    part = MesProductPart(
        part_number="QC-PART-001",
        name="QC Test Part",
        unit="dona",
        created_by="admin",
    )
    db.add(part)
    db.flush()

    template = MesProductTemplate(
        category_id=cat.id,
        code="QC-TPL-B5",
        name="QC Test Template",
        created_by="admin",
    )
    db.add(template)
    db.flush()

    from models import MesBomLine

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
        name="QC Only Route",
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
            stage_id=nazorat.id,
            step_order=0,
            is_required=True,
        )
    )
    db.commit()

    job = MesProductionJob(
        job_number="JOB-B5-TEST",
        template_id=template.id,
        quantity=2.0,
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

    # Operator without QC permission gets 403
    op_token = client.post("/auth/login", json={"username": "tekshiruv1", "password": "1111"})
    assert op_token.status_code == 200, op_token.text
    op_headers = auth_headers(op_token.json()["access_token"])
    r = client.get("/mes/terminal/qc/rejection-reasons", headers=op_headers)
    assert r.status_code == 403, "Operator should need mes_terminal_qc permission"

    admin = db.query(User).filter(User.username == "admin").first()
    from services.permissions import set_user_permissions

    set_user_permissions(
        db,
        admin.id,
        {
            "mes_terminal_qc": True,
            "mes_edit": True,
            "mes_view": True,
            "mes_jobs_manage": True,
        },
    )
    db.commit()

    r = client.get("/mes/terminal/qc/rejection-reasons", headers=headers)
    assert r.status_code == 200, r.text
    reasons = r.json()["reasons"]
    assert len(reasons) >= 1

    r = client.get("/mes/terminal/qc/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    assert "waiting_jobs" in r.json()

    job_id = bootstrap_qc_job(db)

    r = client.get("/mes/terminal/qc/queue", headers=headers)
    assert r.status_code == 200, r.text
    assert any(j["id"] == job_id for j in r.json()["jobs"]), "Job should be in QC queue"

    r = client.post(f"/mes/terminal/qc/jobs/{job_id}/accept", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["step_state"] == "accepted"

    r = client.post(f"/mes/terminal/qc/jobs/{job_id}/start", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["step_state"] == "in_progress"

    bom_line = db.query(MesJobBomLine).filter(MesJobBomLine.job_id == job_id).first()
    assert bom_line

    r = client.put(
        f"/mes/terminal/qc/jobs/{job_id}/quantities",
        headers=headers,
        json={
            "lines": [
                {
                    "bom_line_id": bom_line.id,
                    "accepted_quantity": 1,
                    "rejected_quantity": 0,
                    "rework_quantity": 0,
                }
            ]
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["overall_progress_pct"] == 50.0

    reason_id = reasons[0]["id"]
    r = client.post(
        f"/mes/terminal/qc/jobs/{job_id}/rework",
        headers=headers,
        json={
            "bom_line_id": bom_line.id,
            "quantity": 1,
            "rejection_reason_id": reason_id,
            "notes": "Test rework",
        },
    )
    assert r.status_code == 200, r.text
    rework_id = r.json()["created_rework_id"]
    assert rework_id

    r = client.get("/mes/terminal/qc/rework-queue", headers=headers)
    assert r.status_code == 200, r.text
    assert any(rec["id"] == rework_id for rec in r.json()["records"])

    r = client.post(f"/mes/terminal/qc/rework/{rework_id}/start", headers=headers)
    assert r.status_code == 200, r.text

    r = client.post(f"/mes/terminal/qc/rework/{rework_id}/complete", headers=headers)
    assert r.status_code == 200, r.text

    r = client.put(
        f"/mes/terminal/qc/jobs/{job_id}/quantities",
        headers=headers,
        json={
            "lines": [
                {
                    "bom_line_id": bom_line.id,
                    "accepted_quantity": 1,
                    "rejected_quantity": 0,
                    "rework_quantity": 1,
                }
            ]
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["overall_progress_pct"] == 100.0
    assert r.json().get("auto_completed") is True
    assert r.json()["step_state"] == "completed"

    r = client.post(
        "/mes/qc/rejection-reasons",
        headers=headers,
        json={"name": "Test sabab B5", "sort_order": 99},
    )
    assert r.status_code == 200, r.text

    print("ALL B5 QC TERMINAL TESTS PASSED")
    db.close()
    try:
        os.unlink(TEST_DB)
    except OSError:
        pass


if __name__ == "__main__":
    run_tests()
