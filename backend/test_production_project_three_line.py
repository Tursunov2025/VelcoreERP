"""Three-line ProductionProject progress test on an isolated SQLite database."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
TEST_ROOT = Path(tempfile.mkdtemp(prefix="velcore-three-line-project-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB.replace(chr(92), '/')}",
    "DB_PATH": TEST_DB,
    "DATA_ROOT": str(TEST_ROOT),
    "DATABASE_GUARD": "false",
    "ENVIRONMENT": "test",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from models import (  # noqa: E402
    MesBomLine,
    MesJobPackage,
    MesProductionJob,
    MesProductionRoute,
    MesProductionStage,
    MesProductPart,
    MesProductTemplate,
    MesRouteStep,
    ProductionProject,
    ProductionProjectLine,
)
from services.production_projects import release_project  # noqa: E402
from services.project_execution import project_progress, record_absolute_operation  # noqa: E402


def main() -> None:
    Base.metadata.create_all(engine)
    run_migrations()
    db = SessionLocal()
    try:
        stage = MesProductionStage(name="THREE-LINE-LAZER", department="Kesish")
        db.add(stage)
        db.flush()

        project = ProductionProject(
            project_code="TEST-TOSHKENT-ATLAS-THREE-LINE",
            project_name="Toshkent Atlas",
            customer_name_snapshot="Atlas",
            destination_city="Toshkent",
            site_name="Atlas",
            full_address="Toshkent, Atlas",
            status="planned",
            created_by="test",
        )
        db.add(project)
        db.flush()

        quantities = (2.0, 6.0, 12.0)
        for code, quantity in zip(("Z1", "Z5", "Z8"), quantities):
            product = MesProductTemplate(code=code, name=f"Product {code}", created_by="test")
            detail = MesProductPart(part_number=f"{code}-DETAIL", name=f"{code} detail", created_by="test")
            db.add_all([product, detail])
            db.flush()
            route = MesProductionRoute(
                template_id=product.id,
                name=f"{code} route",
                version=1,
                is_default=True,
                created_by="test",
            )
            db.add(route)
            db.flush()
            product.default_route_id = route.id
            db.add(MesRouteStep(route_id=route.id, stage_id=stage.id, step_order=1, department="Kesish"))
            db.add(MesBomLine(template_id=product.id, part_id=detail.id, required_quantity=1, unit="dona"))
            db.add(ProductionProjectLine(project_id=project.id, product_id=product.id, quantity=quantity))

        db.commit()
        project_id = project.id
        project_version = project.version

        project, release, idempotent = release_project(
            db,
            project_id,
            project_version,
            "three-line-release-1",
            "test",
        )
        assert idempotent is False
        db.commit()

        jobs = db.query(MesProductionJob).filter_by(project_id=project_id).order_by(MesProductionJob.project_line_id).all()
        assert len(jobs) == 3
        assert [float(job.quantity) for job in jobs] == list(quantities)
        assert all(job.project_release_snapshot_id == release.id for job in jobs)

        # Z1 is complete through packaging; Z5 is partial; Z8 has not started.
        z1_line = jobs[0].bom_lines[0]
        record_absolute_operation(db, jobs[0], operation_type="lazer_completed", absolute_quantity=2, username="laser", terminal="LAZER", job_line=z1_line)
        record_absolute_operation(db, jobs[0], operation_type="qc_approved", absolute_quantity=2, username="qc", terminal="QC", job_line=z1_line)
        jobs[0].packages.append(MesJobPackage(
            package_number="Z1-PACKAGE",
            package_type="box",
            quantity=2,
            status="packed",
            project_id=project_id,
            project_line_id=jobs[0].project_line_id,
            project_release_snapshot_id=release.id,
        ))
        record_absolute_operation(db, jobs[0], operation_type="packaged", absolute_quantity=2, username="packager", terminal="PACKAGING")

        z5_line = jobs[1].bom_lines[0]
        record_absolute_operation(db, jobs[1], operation_type="lazer_completed", absolute_quantity=3, username="laser", terminal="LAZER", job_line=z5_line)
        record_absolute_operation(db, jobs[1], operation_type="qc_approved", absolute_quantity=2, username="qc", terminal="QC", job_line=z5_line)
        jobs[1].packages.append(MesJobPackage(
            package_number="Z5-PACKAGE",
            package_type="box",
            quantity=1,
            status="packed",
            project_id=project_id,
            project_line_id=jobs[1].project_line_id,
            project_release_snapshot_id=release.id,
        ))
        record_absolute_operation(db, jobs[1], operation_type="packaged", absolute_quantity=1, username="packager", terminal="PACKAGING")
        db.flush()

        progress = project_progress(db, project)
        lines = sorted(progress["lines"], key=lambda item: item["project_line_id"])
        assert sum(item["required_quantity"] for item in lines) == 20
        assert [item["produced_quantity"] for item in lines] == [2, 3, 0]
        assert [item["qc_approved_quantity"] for item in lines] == [2, 2, 0]
        assert [item["packaged_quantity"] for item in lines] == [2, 1, 0]
        assert progress["overall_progress_percent"] == 17.5
        assert project.status == "partially_ready"

        # Repeating an absolute fact must not double count progress.
        repeated = record_absolute_operation(
            db,
            jobs[1],
            operation_type="lazer_completed",
            absolute_quantity=3,
            username="laser",
            terminal="LAZER",
            job_line=z5_line,
        )
        assert repeated is not None
        assert project_progress(db, project)["overall_progress_percent"] == 17.5
        db.commit()
    finally:
        db.close()

    print("test_production_project_three_line: ALL TESTS PASSED (Z1=2, Z5=6, Z8=12; partial progress=17.5%)")


if __name__ == "__main__":
    main()
