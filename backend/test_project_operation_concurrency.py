"""Independent-session PostgreSQL race for normalized project operation evidence."""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4


POSTGRES_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "").strip()
if not POSTGRES_URL:
    print("test_project_operation_concurrency: SKIPPED (TEST_POSTGRES_DATABASE_URL is absent)")
    raise SystemExit(0)
if not POSTGRES_URL.lower().startswith(("postgresql://", "postgresql+")):
    raise RuntimeError("TEST_POSTGRES_DATABASE_URL must be a PostgreSQL URL")

os.environ.update({
    "DATABASE_URL": POSTGRES_URL,
    "DATABASE_GUARD": "false",
    "ENVIRONMENT": "test",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy.exc import IntegrityError, OperationalError  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from models import (  # noqa: E402
    MesBomLine,
    MesProductionJob,
    MesProductionRoute,
    MesProductionStage,
    MesProductPart,
    MesProductTemplate,
    MesRouteStep,
    ProductionProject,
    ProductionProjectLine,
    ProjectProductionOperation,
)
from services.production_projects import release_project  # noqa: E402
from services.project_execution import ExecutionError, record_absolute_operation  # noqa: E402


def attempt(job_id: int, job_line_id: int, barrier: Barrier, actor: str) -> str:
    db = SessionLocal()
    try:
        from models import MesJobBomLine, MesProductionJob

        job = db.get(MesProductionJob, job_id)
        job_line = db.get(MesJobBomLine, job_line_id)
        barrier.wait(timeout=15)
        record_absolute_operation(
            db,
            job,
            operation_type="lazer_completed",
            absolute_quantity=1,
            username=actor,
            terminal="LAZER",
            job_line=job_line,
        )
        db.commit()
        return "success"
    except (ExecutionError, IntegrityError, OperationalError):
        db.rollback()
        return "rejected"
    finally:
        db.close()


def main() -> None:
    assert engine.dialect.name == "postgresql"
    Base.metadata.create_all(engine)
    run_migrations()
    suffix = uuid4().hex[:12]
    db = SessionLocal()
    try:
        stage = MesProductionStage(name=f"RACE-LAZER-{suffix}", department="Kesish")
        part = MesProductPart(part_number=f"RACE-PART-{suffix}", name="Race part", created_by="test")
        product = MesProductTemplate(code=f"RACE-PRODUCT-{suffix}", name="Race product", created_by="test")
        db.add_all([stage, part, product])
        db.flush()
        route = MesProductionRoute(template_id=product.id, name="Race route", version=1, is_default=True, created_by="test")
        db.add(route)
        db.flush()
        product.default_route_id = route.id
        db.add(MesRouteStep(route_id=route.id, stage_id=stage.id, step_order=1, department="Kesish"))
        db.add(MesBomLine(template_id=product.id, part_id=part.id, required_quantity=1, unit="dona"))
        project = ProductionProject(
            project_code=f"RACE-PROJECT-{suffix}",
            project_name="Operation race",
            customer_name_snapshot="Test",
            status="planned",
            created_by="test",
        )
        db.add(project)
        db.flush()
        db.add(ProductionProjectLine(project_id=project.id, product_id=product.id, quantity=1))
        db.commit()
        project_id = project.id

        project, _, _ = release_project(db, project.id, project.version, f"race-release-{suffix}", "test")
        db.commit()
        job = db.query(MesProductionJob).filter_by(project_id=project_id).one()
        job_id = job.id
        job_line_id = job.bom_lines[0].id
    finally:
        db.close()

    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda actor: attempt(job_id, job_line_id, barrier, actor),
            ("race-a", "race-b"),
        ))

    db = SessionLocal()
    try:
        operations = db.query(ProjectProductionOperation).filter_by(
            project_id=project_id,
            job_line_id=job_line_id,
            operation_type="lazer_completed",
        ).all()
        assert results.count("success") == 1, results
        assert results.count("rejected") == 1, results
        assert len(operations) == 1
        assert sum(float(operation.quantity) for operation in operations) == 1
    finally:
        db.close()

    print(f"test_project_operation_concurrency: PASS (independent PostgreSQL sessions; results={results})")


if __name__ == "__main__":
    main()
