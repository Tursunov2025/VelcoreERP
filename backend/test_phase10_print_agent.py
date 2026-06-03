"""Phase 10 — cloud print queue and agent API lifecycle."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.replace(chr(92), '/')}"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-phase10")
os.environ["PRINT_AGENT_API_KEY"] = "test-print-agent-key"

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import MesJobPackage, MesProductionJob, MesProductCategory, MesProductTemplate, PrintJob  # noqa: E402
from services.package_traceability import create_label_for_package  # noqa: E402
from services.print_jobs import (  # noqa: E402
    complete_print_job,
    create_print_job,
    fail_print_job,
    retry_print_job,
    start_print_job,
)
from services.seed import seed_defaults  # noqa: E402


def setup_db() -> Session:
    Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    seed_defaults(db)
    return db


def agent_headers() -> dict:
    return {"Authorization": "Bearer test-print-agent-key"}


def bootstrap_package(db: Session) -> MesJobPackage:
    suffix = datetime.utcnow().strftime("%H%M%S%f")
    cat = MesProductCategory(name=f"P10 Cat {suffix}", created_by="admin")
    db.add(cat)
    db.flush()
    template = MesProductTemplate(
        category_id=cat.id,
        code=f"P10-{suffix}",
        name="P10 Product",
        created_by="admin",
    )
    db.add(template)
    db.flush()
    job = MesProductionJob(
        job_number=f"JOB-P10-{suffix}",
        template_id=template.id,
        quantity=1.0,
        status="in_progress",
        created_by="admin",
    )
    db.add(job)
    db.flush()
    pkg = MesJobPackage(
        job_id=job.id,
        package_number=f"PACK-P10-{suffix}",
        status="packed",
        net_weight_kg=6.0,
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg


def test_label_creates_print_job(db: Session):
    pkg = bootstrap_package(db)
    with patch("services.label_printer.send_zpl_to_printer"):
        label = create_label_for_package(db, pkg, username="admin", auto_print=True)
    db.commit()
    jobs = db.query(PrintJob).filter(PrintJob.package_id == pkg.id).all()
    assert len(jobs) >= 1
    assert jobs[0].label_code == label.label_code
    assert jobs[0].status in ("pending", "completed")


def test_print_lifecycle_api(client: TestClient, db: Session):
    pkg = bootstrap_package(db)
    job = create_print_job(db, package_id=pkg.id, label_code="PKG-P10-TEST-00001", printer_name="TestPrinter")
    db.commit()
    ah = agent_headers()

    r = client.get("/printing/jobs/pending", headers=ah)
    assert r.status_code == 200, r.text
    assert any(j["id"] == job.id for j in r.json()["jobs"])

    r = client.post(f"/printing/jobs/{job.id}/start", headers=ah)
    assert r.status_code == 200
    assert r.json()["status"] == "printing"

    r = client.get(f"/printing/jobs/{job.id}/label.png", headers=ah)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/")

    r = client.post(f"/printing/jobs/{job.id}/complete", headers=ah)
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    assert r.json()["printed_at"] is not None

    r = client.get("/printing/jobs/pending", headers=ah)
    assert not any(j["id"] == job.id for j in r.json()["jobs"])


def test_failed_and_retry(client: TestClient, db: Session):
    pkg = bootstrap_package(db)
    job = create_print_job(db, package_id=pkg.id, label_code="PKG-P10-FAIL-00001", printer_name="TestPrinter")
    db.commit()
    ah = agent_headers()

    start_print_job(db, job.id)
    db.commit()
    fail_print_job(db, job.id, "Paper out")
    db.commit()

    r = client.post(f"/printing/jobs/{job.id}/failed", headers=ah, json={"error_message": "dup fail ok"})
    assert r.status_code in (200, 400)

    db.refresh(job)
    assert job.status == "failed"

    retry_print_job(db, job.id)
    db.commit()
    db.refresh(job)
    assert job.status == "pending"

    r = client.get("/printing/jobs/pending", headers=ah)
    assert any(j["id"] == job.id for j in r.json()["jobs"])


def test_admin_dashboard_and_reprint(client: TestClient, db: Session):
    token_r = client.post("/auth/login", json={"username": "admin", "password": "1234"})
    assert token_r.status_code == 200
    h = {"Authorization": f"Bearer {token_r.json()['access_token']}"}

    pkg = bootstrap_package(db)
    with patch("services.label_printer.send_zpl_to_printer"):
        label = create_label_for_package(db, pkg, username="admin", auto_print=False)
    db.commit()

    r = client.get("/admin/printing/dashboard", headers=h)
    assert r.status_code == 200
    assert "totals" in r.json()

    r = client.post(f"/packages/{label.label_code}/reprint", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


def main():
    db = setup_db()
    client = TestClient(app)
    test_label_creates_print_job(db)
    test_print_lifecycle_api(client, db)
    test_failed_and_retry(client, db)
    test_admin_dashboard_and_reprint(client, db)
    print("test_phase10_print_agent: OK")


if __name__ == "__main__":
    main()
