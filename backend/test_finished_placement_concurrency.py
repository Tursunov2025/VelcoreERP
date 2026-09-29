"""Independent-session finished placement race; PostgreSQL-only deployment gate."""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

POSTGRES_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "").strip()
if not POSTGRES_URL:
    print("test_finished_placement_concurrency: SKIPPED (TEST_POSTGRES_DATABASE_URL is absent)")
    raise SystemExit(0)
if not POSTGRES_URL.lower().startswith(("postgresql://", "postgresql+")):
    raise RuntimeError("TEST_POSTGRES_DATABASE_URL must be a PostgreSQL URL")

os.environ.update({"DATABASE_URL": POSTGRES_URL, "DATABASE_GUARD": "false", "ENVIRONMENT": "test"})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy.exc import IntegrityError, OperationalError  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from models import (  # noqa: E402
    MesFinishedGoodsPlacement, MesJobPackage, MesJobRouteStep, MesProductionJob,
    MesProductionStage, MesProductTemplate, MesWarehouseLocation, ProductionProject,
    ProductionProjectLine, ProjectReleaseSnapshot,
)
from services.mes_warehouse_terminal import assign_package_to_location, warehouse_stage_ids  # noqa: E402


def attempt(job_id: int, package_id: int, location_id: int, barrier: Barrier, actor: str) -> str:
    db = SessionLocal()
    try:
        job = db.get(MesProductionJob, job_id)
        barrier.wait(timeout=15)
        assign_package_to_location(db, job, warehouse_stage_ids(db), actor,
                                   package_id=package_id, location_id=location_id)
        db.commit()
        return "success"
    except (ValueError, IntegrityError, OperationalError):
        db.rollback()
        return "rejected"
    finally:
        db.close()


def main() -> None:
    assert engine.dialect.name == "postgresql"
    Base.metadata.create_all(engine); run_migrations()
    suffix = uuid4().hex[:12]
    db = SessionLocal()
    try:
        template = MesProductTemplate(code=f"PLACE-{suffix}", name="Placement race", created_by="test")
        project = ProductionProject(project_code=f"PLACE-PROJECT-{suffix}", project_name="Placement race",
                                    customer_name_snapshot="Test", status="released", release_revision=1,
                                    created_by="test")
        location = MesWarehouseLocation(code=f"FG-{suffix}", segment_code=f"FG-{suffix}",
                                        location_type="warehouse", is_active=True, created_by="test")
        db.add_all([template, project, location]); db.flush()
        line = ProductionProjectLine(project_id=project.id, product_id=template.id, quantity=1, status="released")
        release = ProjectReleaseSnapshot(project_id=project.id, revision=1, source_project_version=1,
                                         idempotency_key=f"place-release-{suffix}", checksum="0" * 64,
                                         released_by="test")
        db.add_all([line, release]); db.flush()
        job = MesProductionJob(job_number=f"PLACE-JOB-{suffix}", customer_name="Test", template_id=template.id,
                               quantity=1, status="in_progress", created_by="test", project_id=project.id,
                               project_line_id=line.id, project_release_snapshot_id=release.id)
        db.add(job); db.flush()
        stage = db.query(MesProductionStage).filter_by(name="Sklad").first()
        if not stage:
            stage = MesProductionStage(name="Sklad", department="Ombor", is_active=True)
            db.add(stage); db.flush()
        db.add(MesJobRouteStep(job_id=job.id, stage_id=stage.id, stage_name="Sklad", step_order=1,
                               department="Ombor", accepted_at=project.created_at, started_at=project.created_at))
        package = MesJobPackage(job_id=job.id, package_number=f"PLACE-PKG-{suffix}", quantity=1,
                                status="received", project_id=project.id, project_line_id=line.id,
                                project_release_snapshot_id=release.id)
        db.add(package); db.commit()
        job_id, package_id, location_id = job.id, package.id, location.id
    finally:
        db.close()

    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, job_id, package_id, location_id, barrier, actor)
                   for actor in ("placer-a", "placer-b")]
        results = [future.result() for future in futures]
    db = SessionLocal()
    try:
        rows = db.query(MesFinishedGoodsPlacement).filter_by(package_id=package_id).all()
        assert results.count("success") == 1, results
        assert results.count("rejected") == 1, results
        assert len(rows) == 1 and float(rows[0].quantity) == 1
    finally:
        db.close()
    print(f"test_finished_placement_concurrency: PASS (independent PostgreSQL sessions; results={results})")


if __name__ == "__main__": main()
