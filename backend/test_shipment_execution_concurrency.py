"""Independent-session Checkpoint C races; PostgreSQL-only pre-deployment gate."""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

POSTGRES_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "").strip()
if not POSTGRES_URL:
    print("test_shipment_execution_concurrency: SKIPPED (TEST_POSTGRES_DATABASE_URL is absent)")
    raise SystemExit(0)
if not POSTGRES_URL.lower().startswith(("postgresql://", "postgresql+")):
    raise RuntimeError("TEST_POSTGRES_DATABASE_URL must be a PostgreSQL URL")
os.environ.update({"DATABASE_URL": POSTGRES_URL, "DATABASE_GUARD": "false", "ENVIRONMENT": "test"})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy.exc import IntegrityError, OperationalError  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from models import (  # noqa: E402
    MesBomLine, MesFinishedGoodsInventory, MesFinishedGoodsPlacement, MesInventoryMovement,
    MesJobPackage, MesLoadingPlanPlacement, MesProductionJob, MesProductionRoute,
    MesProductionStage, MesProductPart, MesProductTemplate, MesRouteStep, MesShipmentItem,
    MesTrip, MesTripCommand, MesVehicle, MesWarehouseLocation, ProductionProject,
    ProductionProjectLine, ProjectProductionOperation,
)
from services.finished_logistics import create_trip, create_vehicle, transition_trip  # noqa: E402
from services.production_projects import release_project  # noqa: E402
from services.project_execution import record_absolute_operation  # noqa: E402
from services.shipment_execution import (  # noqa: E402
    ShipmentError, accept_delivery, assign_placement, confirm_loading, final_dispatch,
    record_delivery, save_plan,
)


def race(worker):
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result() for future in [pool.submit(worker, barrier, index) for index in (1, 2)]]
    assert results.count("success") == 1 and results.count("rejected") == 1, results
    return results


def session_attempt(barrier, action):
    db = SessionLocal()
    try:
        barrier.wait(timeout=20); action(db); db.commit(); return "success"
    except (ShipmentError, IntegrityError, OperationalError, ValueError):
        db.rollback(); return "rejected"
    finally: db.close()


def main() -> None:
    assert engine.dialect.name == "postgresql"
    Base.metadata.create_all(engine); run_migrations(); suffix = uuid4().hex[:10]
    db = SessionLocal()
    stage = MesProductionStage(name=f"C-RACE-LAZER-{suffix}", department="Kesish", is_active=True)
    product = MesProductTemplate(code=f"C-RACE-{suffix}", name="Race product", length_mm=1000,
                                 width_mm=500, height_mm=500, created_by="test")
    part = MesProductPart(part_number=f"C-RACE-PART-{suffix}", name="Race part", created_by="test")
    db.add_all([stage, product, part]); db.flush()
    route = MesProductionRoute(template_id=product.id, name="Race route", version=1, is_default=True, created_by="test")
    db.add(route); db.flush(); product.default_route_id = route.id
    db.add(MesRouteStep(route_id=route.id, stage_id=stage.id, step_order=1, department="Kesish"))
    db.add(MesBomLine(template_id=product.id, part_id=part.id, required_quantity=1, unit="dona"))
    project = ProductionProject(project_code=f"C-RACE-PROJECT-{suffix}", project_name="Race",
                                customer_name_snapshot="Race", destination_city="Toshkent",
                                site_name="Atlas", full_address="Toshkent, Atlas", status="planned", created_by="test")
    db.add(project); db.flush(); db.add(ProductionProjectLine(project_id=project.id, product_id=product.id, quantity=1, status="planned")); db.commit()
    project, release, _ = release_project(db, project.id, project.version, f"c-race-release-{suffix}", "test"); db.commit()
    job = db.query(MesProductionJob).filter_by(project_id=project.id).one(); job_line = job.bom_lines[0]
    record_absolute_operation(db, job, operation_type="lazer_completed", absolute_quantity=1, username="test", terminal="LAZER", job_line=job_line)
    record_absolute_operation(db, job, operation_type="qc_approved", absolute_quantity=1, username="test", terminal="QC", job_line=job_line)
    location = MesWarehouseLocation(code=f"C-RACE-LOC-{suffix}", segment_code=f"LOC-{suffix}", location_type="warehouse", created_by="test")
    db.add(location); db.flush()
    package = MesJobPackage(job_id=job.id, package_number=f"C-RACE-PKG-{suffix}", quantity=1, gross_weight_kg=10,
                            status="placed", location_id=location.id, project_id=project.id,
                            project_line_id=job.project_line_id, project_release_snapshot_id=release.id)
    db.add(package); db.flush()
    inventory = MesFinishedGoodsInventory(job_id=job.id, package_id=package.id, template_id=product.id,
                                          product_code=product.code, product_name=product.name, location_id=location.id,
                                          quantity=1, status="in_stock", created_by="test", project_id=project.id,
                                          project_line_id=job.project_line_id, project_release_snapshot_id=release.id)
    db.add(inventory); db.flush()
    placement = MesFinishedGoodsPlacement(inventory_id=inventory.id, package_id=package.id, location_id=location.id,
                                          project_id=project.id, project_line_id=job.project_line_id, template_id=product.id,
                                          release_id=release.id, quantity=1, status="placed", placed_by="test", updated_by="test")
    vehicle_data = SimpleNamespace(vehicle_type="truck", registration_number=f"C{suffix}", driver_name="Driver",
                                   driver_phone="", max_payload_kg=1000, internal_length_mm=5000,
                                   internal_width_mm=2000, internal_height_mm=2000, max_volume_m3=None, is_active=True)
    vehicle = create_vehicle(db, vehicle_data, "test")
    trip_data = SimpleNamespace(trip_number=f"C-RACE-TRIP-{suffix}", vehicle_id=vehicle.id, project_id=project.id,
                                release_id=release.id, destination_city="Toshkent", destination_site="Atlas",
                                destination_address="Toshkent, Atlas", planned_departure_at=None, notes="")
    trip = create_trip(db, trip_data, "test"); trip.evidence_policy = "optional"; db.add(placement); db.commit()
    trip_id, placement_id = trip.id, placement.id

    race(lambda barrier, index: session_attempt(barrier, lambda s: assign_placement(
        s, trip_id, placement_id, dispatch_id=None, planned_quantity=None,
        idempotency_key=f"c-race-assign-{suffix}-{index}", actor=f"actor-{index}")))
    db.expire_all(); item = db.query(MesShipmentItem).filter_by(trip_id=trip_id).one(); item_id = item.id
    assert db.query(MesShipmentItem).filter_by(trip_id=trip_id).count() == 1

    plan = [{"shipment_item_id": item_id, "x_mm": 0, "y_mm": 0, "rotation": 0, "loading_sequence": 1}]
    race(lambda barrier, index: session_attempt(barrier, lambda s: save_plan(s, trip_id, plan, f"planner-{index}")))
    assert db.query(MesLoadingPlanPlacement).filter_by(trip_id=trip_id).count() == 1

    trip = db.get(MesTrip, trip_id); transition_trip(db, trip, "planned", trip.version, "test")
    transition_trip(db, trip, "loading", trip.version, "test"); db.commit()
    race(lambda barrier, index: session_attempt(barrier, lambda s: confirm_loading(
        s, trip_id, acknowledge_unknown_weight=True, idempotency_key=f"c-race-load-{suffix}-{index}", actor=f"loader-{index}")))
    assert db.query(MesInventoryMovement).filter_by(package_id=package.id, movement_type="trip_load").count() == 1

    race(lambda barrier, index: session_attempt(barrier, lambda s: final_dispatch(
        s, trip_id, idempotency_key=f"c-race-dispatch-{suffix}-{index}", actor=f"dispatch-{index}")))
    assert db.query(MesInventoryMovement).filter_by(package_id=package.id, movement_type="trip_dispatch").count() == 1
    trip = db.get(MesTrip, trip_id); transition_trip(db, trip, "in_transit", trip.version, "test"); db.commit()
    disposition = [{"item_id": item_id, "delivered_quantity": 1, "accepted_quantity": 1,
                    "damaged_quantity": 0, "missing_quantity": 0, "notes": ""}]
    race(lambda barrier, index: session_attempt(barrier, lambda s: record_delivery(
        s, trip_id, disposition, idempotency_key=f"c-race-delivery-{suffix}-{index}", actor=f"driver-{index}")))
    assert db.query(MesInventoryMovement).filter_by(package_id=package.id, movement_type="trip_delivery").count() == 1
    race(lambda barrier, index: session_attempt(barrier, lambda s: accept_delivery(
        s, trip_id, recipient_name="Receiver", notes="", resolved_shortage_item_ids=[],
        idempotency_key=f"c-race-accept-{suffix}-{index}", actor=f"receiver-{index}")))
    assert db.query(MesTripCommand).filter(MesTripCommand.trip_id == trip_id,
                                          MesTripCommand.command_type.in_(("confirm_loading", "dispatch", "delivery", "acceptance"))).count() == 4
    assert db.query(ProjectProductionOperation).filter_by(project_id=project.id, operation_type="trip_loaded").count() == 1
    db.close()
    print("test_shipment_execution_concurrency: PASS (assignment, plan claim, loading, dispatch, delivery, acceptance)")


if __name__ == "__main__": main()
