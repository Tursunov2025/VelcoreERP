"""Minimal synthetic Checkpoint E acceptance data for an explicitly disposable DB."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def require_disposable_database() -> Path:
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("sqlite:///"):
        raise SystemExit("Checkpoint E fixture requires an explicit SQLite DATABASE_URL")
    path = Path(url.removeprefix("sqlite:///")).resolve()
    normalized = str(path).replace("\\", "/").lower()
    allowed_roots = ("/temp/azmus-checkpoint-e-", "/temp/azmus-repair-r1-")
    if not any(marker in normalized for marker in allowed_roots):
        raise SystemExit(f"Refusing non-acceptance-temp path: {path}")
    production = Path(r"D:\AzmusERP\Data\database\azmus.db").resolve()
    if path == production:
        raise SystemExit("Refusing production database")
    return path


DB_PATH = require_disposable_database()

from auth.security import hash_password  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from models import (  # noqa: E402
    MesBomLine, MesFinishedGoodsInventory, MesFinishedGoodsPlacement, MesJobPackage,
    MesProductionJob, MesProductionRoute, MesProductionStage, MesProductPart,
    MesProductTemplate, MesRouteStep, MesVehicle, MesWarehouseLocation,
    ProductionProject, User,
)
from services.project_execution import record_absolute_operation  # noqa: E402
from services.mes_packaging_terminal import (  # noqa: E402
    accept_packaging_job, complete_packaging_job, packaging_stage_ids,
    start_packaging_job, update_packaging_data,
)
from services.mes_warehouse_terminal import (  # noqa: E402
    accept_warehouse_receipt, assign_package_to_location,
    start_warehouse_placement, warehouse_stage_ids,
)


PRODUCTS = {
    "TEST-Z1": (2.0, 1000.0, 500.0, 500.0, 100.0),
    "TEST-Z5": (5.0, 1500.0, 700.0, 700.0, 200.0),
    "TEST-Z8": (10.0, 3000.0, 1000.0, 900.0, 500.0),
}


def seed_master() -> None:
    Base.metadata.create_all(engine); run_migrations(); db = SessionLocal()
    try:
        if not db.query(User).filter_by(username="TEST-E2E-ADMIN").first():
            db.add(User(username="TEST-E2E-ADMIN", password_hash=hash_password("TestE2E123!"), role="admin", department="Admin"))
        def ensure_stage(name: str, department: str, order: int):
            row = db.query(MesProductionStage).filter_by(name=name).first()
            if not row:
                row = MesProductionStage(name=name, department=department, sort_order=order, is_active=True)
                db.add(row); db.flush()
            return row
        lazer_stage = ensure_stage("Lazer", "Kesish", 1)
        welding_stage = ensure_stage("Svarshik", "Svarka", 2)
        paint_stage = ensure_stage("Kraska", "Kraska", 3)
        qc_stage = ensure_stage("Nazorat", "Tekshiruv", 4)
        packaging_stage = ensure_stage("Upakovka", "Upakovka", 5)
        warehouse_stage = ensure_stage("Sklad", "Ombor", 6)
        for code, (_qty, length, width, height, weight) in PRODUCTS.items():
            if db.query(MesProductTemplate).filter_by(code=code).first():
                continue
            product = MesProductTemplate(code=code, name=f"Synthetic acceptance {code}", length_mm=length,
                                         width_mm=width, height_mm=height, weight_kg=weight, created_by="TEST-E2E")
            part = MesProductPart(part_number=f"{code}-DETAIL", name=f"Synthetic {code} detail", created_by="TEST-E2E")
            db.add_all([product, part]); db.flush()
            route = MesProductionRoute(template_id=product.id, name=f"{code} acceptance route", version=1,
                                       is_default=True, is_active=True, created_by="TEST-E2E")
            db.add(route); db.flush(); product.default_route_id = route.id
            db.add_all([
                MesRouteStep(route_id=route.id, stage_id=lazer_stage.id, step_order=1, department="Kesish"),
                MesRouteStep(route_id=route.id, stage_id=welding_stage.id, step_order=2, department="Svarka"),
                MesRouteStep(route_id=route.id, stage_id=paint_stage.id, step_order=3, department="Kraska"),
                MesRouteStep(route_id=route.id, stage_id=qc_stage.id, step_order=4, department="Tekshiruv"),
                MesRouteStep(route_id=route.id, stage_id=packaging_stage.id, step_order=5, department="Upakovka"),
                MesRouteStep(route_id=route.id, stage_id=warehouse_stage.id, step_order=6, department="Ombor"),
            ])
            db.add(MesBomLine(template_id=product.id, part_id=part.id, required_quantity=1, unit="dona"))
        parent = None
        segments = [("warehouse", "TEST-FG"), ("zone", "ZONE-A"), ("aisle", "AISLE-01"),
                    ("rack", "RACK-01"), ("bin", "BIN-01")]
        code_parts = []
        for kind, segment in segments:
            code_parts.append(segment)
            code = "-".join(code_parts)
            row = db.query(MesWarehouseLocation).filter_by(code=code).first()
            if not row:
                row = MesWarehouseLocation(code=code, segment_code=segment, location_type=kind,
                                           parent_id=parent.id if parent else None, description="TEST-E2E only",
                                           is_active=True, created_by="TEST-E2E")
                db.add(row); db.flush()
            parent = row
        if not db.query(MesVehicle).filter_by(registration_number="TEST-E2E-TRUCK").first():
            db.add(MesVehicle(vehicle_type="TEST truck", registration_number="TEST-E2E-TRUCK",
                              driver_name="TEST Driver", driver_phone="TEST-PHONE", max_payload_kg=20000,
                              internal_length_mm=13600, internal_width_mm=2450, internal_height_mm=2700,
                              max_volume_m3=80, is_active=True, version=1,
                              created_by="TEST-E2E", updated_by="TEST-E2E"))
        db.commit()
        print(f"Checkpoint E master fixture ready: {DB_PATH}")
    finally:
        db.close()


def stage_project(project_code: str) -> None:
    db = SessionLocal()
    try:
        project = db.query(ProductionProject).filter_by(project_code=project_code).one()
        if project.destination_city != "TEST-Toshkent" or project.site_name != "TEST-Atlas":
            raise SystemExit("Refusing to stage a non-TEST destination")
        location = db.query(MesWarehouseLocation).filter_by(code="TEST-FG-ZONE-A-AISLE-01-RACK-01-BIN-01").one()
        jobs = db.query(MesProductionJob).filter_by(project_id=project.id).all()
        for job in jobs:
            qty, _length, _width, _height, weight = PRODUCTS[job.template.code]
            if db.query(MesFinishedGoodsPlacement).filter_by(project_line_id=job.project_line_id).first():
                continue
            line = job.bom_lines[0]
            production_quantity = float(
                line.production_required_quantity
                if line.production_required_quantity is not None
                else qty
            )
            record_absolute_operation(db, job, operation_type="lazer_completed", absolute_quantity=production_quantity,
                                      username="TEST-E2E", terminal="LAZER", job_line=line)
            record_absolute_operation(db, job, operation_type="qc_approved", absolute_quantity=qty,
                                      username="TEST-E2E", terminal="QC", job_line=line)
            # The fixture may synthesize prerequisite production evidence, but
            # packaging, receipt and placement must use the real service path.
            now = datetime.utcnow()
            for step in sorted(job.route_steps, key=lambda item: item.step_order):
                if step.department == "Kesish":
                    step.accepted_at = step.accepted_at or now
                    step.started_at = step.started_at or now
                    step.completed_at = step.completed_at or now
            pids = packaging_stage_ids(db)
            accept_packaging_job(db, job, pids, "TEST-E2E")
            start_packaging_job(db, job, pids, "TEST-E2E")
            update_packaging_data(db, job, pids, "TEST-E2E", package_type="TEST", package_count=1,
                                  net_weight_kg=weight, gross_weight_kg=weight, packaged_quantity=qty)
            db.flush(); db.expire(job, ["packages"])
            complete_packaging_job(db, job, pids, "TEST-E2E")
            wids = warehouse_stage_ids(db)
            accept_warehouse_receipt(db, job, wids, "TEST-E2E")
            start_warehouse_placement(db, job, wids, "TEST-E2E")
            package = next(pkg for pkg in job.packages if pkg.status == "received")
            assign_package_to_location(db, job, wids, "TEST-E2E", package_id=package.id, location_id=location.id)
        db.commit()
        print(f"Checkpoint E project staged: {project.project_code}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("seed-master", "stage-project"))
    parser.add_argument("--project-code")
    args = parser.parse_args()
    if args.command == "seed-master": seed_master()
    elif not args.project_code: parser.error("--project-code is required")
    else: stage_project(args.project_code)
