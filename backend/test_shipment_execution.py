"""Checkpoint C three-line transactional shipment and 2D-plan acceptance test."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

DB = os.getenv("PHASE5_E2E_DB") or tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
ROOT = Path(os.getenv("PHASE5_E2E_ROOT") or tempfile.mkdtemp(prefix="velcore-shipment-execution-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB.replace(chr(92), '/')}", "DB_PATH": DB,
    "DATA_ROOT": str(ROOT), "DATABASE_GUARD": "false", "ENVIRONMENT": "test",
    "JWT_SECRET_KEY": "shipment-execution-secret",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402
from auth.security import hash_password  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    MesBomLine, MesDispatch, MesFinishedGoodsInventory, MesFinishedGoodsPlacement, MesInventoryMovement,
    MesJobPackage, MesProductionJob, MesProductionRoute, MesProductionStage, MesProductPart,
    MesProductTemplate, MesRouteStep, MesShipmentItem, MesTripCommand, MesVehicle,
    MesTripEvidence, MesTripLatestLocation, MesTripLocation, MesTripTrackingSession,
    MesWarehouseLocation, ProductionProject, ProductionProjectLine, ProjectDetailRequirement,
    ProjectLineBomSnapshot, ProjectProductionOperation, ProjectStockAllocation,
    User, WarehouseStock, WarehouseTransaction,
)
from services.finished_logistics import create_trip, create_vehicle, save_trip_evidence, transition_trip  # noqa: E402
from services.production_projects import release_project  # noqa: E402
from services.project_execution import consume_project_stock, record_absolute_operation, reconcile_project_line  # noqa: E402
from services.shipment_execution import (  # noqa: E402
    ShipmentError, accept_delivery, assign_placement, automatic_initial_plan,
    confirm_loading, final_dispatch, record_delivery, save_plan, validate_plan,
)
from services.trip_lifecycle import confirm_arrival  # noqa: E402
from services.trip_tracking import append_locations, start_session  # noqa: E402


def expect(code: str, fn) -> None:
    try:
        fn(); raise AssertionError(f"Expected {code}")
    except ShipmentError as exc:
        assert exc.code == code, (exc.code, code, str(exc))


def add_finished(db, job, package_number: str, quantity: float, location, gross_weight: float | None):
    package = MesJobPackage(job_id=job.id, package_number=package_number, quantity=quantity,
                            gross_weight_kg=gross_weight or 0, status="placed", location_id=location.id,
                            project_id=job.project_id, project_line_id=job.project_line_id,
                            project_release_snapshot_id=job.project_release_snapshot_id)
    db.add(package); db.flush()
    packaged_total = sum(float(row.quantity or 0) for row in job.packages if row.status != "cancelled")
    record_absolute_operation(db, job, operation_type="packaged", absolute_quantity=packaged_total,
                              username="packager", terminal="PACKAGING")
    inventory = MesFinishedGoodsInventory(job_id=job.id, package_id=package.id, template_id=job.template_id,
                                          product_code=job.template.code, product_name=job.template.name,
                                          location_id=location.id, quantity=quantity, status="in_stock",
                                          created_by="warehouse", project_id=job.project_id,
                                          project_line_id=job.project_line_id,
                                          project_release_snapshot_id=job.project_release_snapshot_id)
    db.add(inventory); db.flush()
    placement = MesFinishedGoodsPlacement(inventory_id=inventory.id, package_id=package.id,
                                          location_id=location.id, project_id=job.project_id,
                                          project_line_id=job.project_line_id, template_id=job.template_id,
                                          release_id=job.project_release_snapshot_id, quantity=quantity,
                                          status="placed", placed_by="warehouse", updated_by="warehouse")
    db.add(placement); db.flush()
    return placement


def main() -> None:
    Base.metadata.create_all(engine); run_migrations(); run_migrations(); db = SessionLocal()
    db.add_all([
        User(username="ship-admin", password_hash=hash_password("Ship123!"), role="admin", department="Admin"),
        User(username="ship-denied", password_hash=hash_password("Denied123!"), role="operator", department="Kesish"),
        User(username="ship-driver", password_hash=hash_password("Driver123!"), role="driver", department="Logistika"),
    ])
    db.flush()
    driver = db.query(User).filter_by(username="ship-driver").one()
    stage = MesProductionStage(name="SHIP-LAZER", department="Kesish", is_active=True)
    shared = MesProductPart(part_number="SHIP-SHARED", name="Reusable shared detail", created_by="test")
    db.add_all([stage, shared]); db.flush()
    shared_stock = WarehouseStock(detail_id=shared.id, detail_code=shared.part_number, detail_name=shared.name,
                                  quantity=5, reserved_quantity=0, unit="dona", status="READY")
    db.add(shared_stock)
    specs = {
        "Z1": (2.0, 1000.0, 500.0, 500.0),
        "Z5": (5.0, 1500.0, 700.0, 700.0),
        "Z8": (10.0, 3000.0, 1000.0, 900.0),
    }
    products = {}
    for code, (_, length, width, height) in specs.items():
        product = MesProductTemplate(code=code, name=f"Product {code}", length_mm=length,
                                     width_mm=width, height_mm=height, weight_kg=None, created_by="test")
        detail = MesProductPart(part_number=f"{code}-DETAIL", name=f"{code} detail", created_by="test")
        db.add_all([product, detail]); db.flush()
        route = MesProductionRoute(template_id=product.id, name=f"{code} route", version=1,
                                   is_default=True, created_by="test")
        db.add(route); db.flush(); product.default_route_id = route.id
        db.add(MesRouteStep(route_id=route.id, stage_id=stage.id, step_order=1, department="Kesish"))
        db.add_all([
            MesBomLine(template_id=product.id, part_id=detail.id, required_quantity=1, unit="dona", sort_order=1),
            MesBomLine(template_id=product.id, part_id=shared.id, required_quantity=1, unit="dona", sort_order=2),
        ])
        products[code] = product
    project = ProductionProject(project_code="SHIP-ATLAS", project_name="Toshkent Atlas",
                                customer_name_snapshot="Atlas", destination_city="Toshkent",
                                site_name="Atlas", full_address="Toshkent, Atlas", status="planned",
                                created_by="test")
    db.add(project); db.flush()
    for code, (quantity, *_dims) in specs.items():
        db.add(ProductionProjectLine(project_id=project.id, product_id=products[code].id,
                                     quantity=quantity, status="planned"))
    db.commit()
    project, release, _ = release_project(db, project.id, project.version, "ship-release-1", "planner")
    db.commit()
    jobs = {job.template.code: job for job in db.query(MesProductionJob).filter_by(project_id=project.id).all()}
    shared_requirement = db.query(ProjectDetailRequirement).filter_by(
        release_id=release.id, detail_id=shared.id).one()
    shared_allocation = db.query(ProjectStockAllocation).filter_by(requirement_id=shared_requirement.id).one()
    assert shared_requirement.gross_required_quantity == 17
    assert shared_requirement.stock_reserved_quantity == 5
    assert shared_requirement.production_required_quantity == 12
    assert db.query(ProjectLineBomSnapshot).filter_by(release_id=release.id).count() == 6
    assert shared_stock.quantity == 5 and shared_stock.reserved_quantity == 5
    assert db.query(WarehouseTransaction).filter_by(stock_id=shared_stock.id, operation="RESERVE").count() == 1
    for job in jobs.values():
        shared_line = next(line for line in job.bom_lines if line.part_id == shared.id)
        produced = float(shared_line.production_required_quantity or 0)
        stocked = float(shared_line.stock_reserved_quantity or 0)
        if produced:
            record_absolute_operation(db, job, operation_type="lazer_completed", absolute_quantity=produced,
                                      username="laser", terminal="LAZER", job_line=shared_line)
        if stocked:
            assert consume_project_stock(db, job, shared.id, stocked, "welder") == stocked
        record_absolute_operation(db, job, operation_type="svarka_ready", absolute_quantity=float(shared_line.allocated_quantity),
                                  username="welder", terminal="SVARKA", job_line=shared_line)
        record_absolute_operation(db, job, operation_type="svarka_accepted", absolute_quantity=float(shared_line.allocated_quantity),
                                  username="welder", terminal="SVARKA", job_line=shared_line)
        record_absolute_operation(db, job, operation_type="qc_approved", absolute_quantity=float(shared_line.allocated_quantity),
                                  username="qc", terminal="QC", job_line=shared_line)
    db.commit()
    db.refresh(shared_stock); db.refresh(shared_allocation); db.refresh(shared_requirement)
    assert shared_allocation.consumed_quantity == 5 and shared_requirement.consumed_quantity == 5
    assert shared_stock.quantity == 0 and shared_stock.reserved_quantity == 0
    assert sum(row.quantity for row in db.query(WarehouseTransaction).filter_by(
        stock_id=shared_stock.id, operation="OUT").all()) == 5

    # Partial production and rework gate.
    z1 = jobs["Z1"]; z5 = jobs["Z5"]; z8 = jobs["Z8"]
    record_absolute_operation(db, z1, operation_type="lazer_completed", absolute_quantity=2,
                              username="laser", terminal="LAZER", job_line=z1.bom_lines[0])
    record_absolute_operation(db, z1, operation_type="qc_approved", absolute_quantity=2,
                              username="qc", terminal="QC", job_line=z1.bom_lines[0])
    record_absolute_operation(db, z5, operation_type="lazer_completed", absolute_quantity=3,
                              username="laser", terminal="LAZER", job_line=z5.bom_lines[0])
    record_absolute_operation(db, z5, operation_type="qc_approved", absolute_quantity=2,
                              username="qc", terminal="QC", job_line=z5.bom_lines[0])
    record_absolute_operation(db, z5, operation_type="rework_created", absolute_quantity=1,
                              username="qc", terminal="QC", job_line=z5.bom_lines[0])
    location = MesWarehouseLocation(code="FG-C1", segment_code="FG-C1", location_type="warehouse",
                                    is_active=True, created_by="test")
    db.add(location); db.flush()
    z1p = add_finished(db, z1, "Z1-P1", 2, location, 100)
    z5p1 = add_finished(db, z5, "Z5-P1", 3, location, None)
    db.commit()

    vehicle_data = SimpleNamespace(vehicle_type="truck", registration_number="01C001AA",
                                   driver_name="Driver", driver_phone="+99890", max_payload_kg=20000,
                                   internal_length_mm=13600, internal_width_mm=2450,
                                   internal_height_mm=2700, max_volume_m3=None, is_active=True)
    vehicle = create_vehicle(db, vehicle_data, "planner")
    trip_data = SimpleNamespace(trip_number="TRIP-C-1", vehicle_id=vehicle.id, driver_user_id=driver.id,
                                project_id=project.id,
                                release_id=release.id, destination_city="Toshkent", destination_site="Atlas",
                                destination_address="Toshkent, Atlas", planned_departure_at=None, notes="")
    trip = create_trip(db, trip_data, "planner"); trip.evidence_policy = "required"; db.commit()
    dispatch = MesDispatch(dispatch_number="SHIP-C-DISPATCH-Z1", job_id=z1.id, customer_name="Atlas",
                           status="pending", created_by="planner", project_id=project.id,
                           destination_city="Toshkent", site_name="Atlas", trip_id=trip.id)
    db.add(dispatch); db.commit()

    first = assign_placement(db, trip.id, z1p.id, dispatch_id=dispatch.id, planned_quantity=None,
                             idempotency_key="assign-z1-0001", actor="planner")
    db.commit(); first_retry = assign_placement(db, trip.id, z1p.id, dispatch_id=dispatch.id, planned_quantity=None,
                                                idempotency_key="assign-z1-0001", actor="planner")
    assert first_retry["idempotent"] is True and first_retry["item"]["id"] == first["item"]["id"]
    expect("shipment_item_not_finished", lambda: assign_placement(
        db, trip.id, z5p1.id, dispatch_id=None, planned_quantity=None,
        idempotency_key="assign-z5-blocked", actor="planner"))
    db.rollback()

    # Complete rework/production and finish the remaining packages.
    record_absolute_operation(db, z5, operation_type="rework_completed", absolute_quantity=1,
                              username="qc", terminal="QC", job_line=z5.bom_lines[0])
    record_absolute_operation(db, z5, operation_type="lazer_completed", absolute_quantity=5,
                              username="laser", terminal="LAZER", job_line=z5.bom_lines[0])
    record_absolute_operation(db, z5, operation_type="qc_approved", absolute_quantity=5,
                              username="qc", terminal="QC", job_line=z5.bom_lines[0])
    record_absolute_operation(db, z8, operation_type="lazer_completed", absolute_quantity=10,
                              username="laser", terminal="LAZER", job_line=z8.bom_lines[0])
    record_absolute_operation(db, z8, operation_type="qc_approved", absolute_quantity=10,
                              username="qc", terminal="QC", job_line=z8.bom_lines[0])
    # Project-level production readiness combines LAZER evidence with the
    # reusable stock portion, but remains capped by each ordered line.
    readiness = [reconcile_project_line(db, line) for line in project.lines]
    assert [row["produced_quantity"] for row in readiness] == [2, 5, 10]
    assert all(row["produced_quantity"] <= row["required_quantity"] for row in readiness)
    assert sum(float(row.quantity) for row in db.query(WarehouseTransaction).filter_by(
        stock_id=shared_stock.id, operation="OUT").all()) == 5
    z5p2 = add_finished(db, z5, "Z5-P2", 2, location, 200)
    z8p = add_finished(db, z8, "Z8-P1", 10, location, 500)
    db.commit()

    # Snapshot mismatch rolls back the claim.
    z5p1.release_id = None; db.commit()
    expect("shipment_item_mismatch", lambda: assign_placement(
        db, trip.id, z5p1.id, dispatch_id=None, planned_quantity=None,
        idempotency_key="assign-z5-mismatch", actor="planner"))
    db.rollback(); z5p1 = db.get(MesFinishedGoodsPlacement, z5p1.id); z5p1.release_id = release.id; db.commit()
    for key, placement in (("z5a", z5p1), ("z5b", z5p2), ("z8", z8p)):
        assign_placement(db, trip.id, placement.id, dispatch_id=None, planned_quantity=None,
                         idempotency_key=f"assign-{key}-0001", actor="planner")
        db.commit()
    items = db.query(MesShipmentItem).filter_by(trip_id=trip.id).order_by(MesShipmentItem.id).all()
    assert sum(item.planned_quantity for item in items) == 17
    assert sum(item.gross_weight_kg is None for item in items) == 1

    auto1 = automatic_initial_plan(db, trip); auto2 = automatic_initial_plan(db, trip)
    assert auto1 == auto2 and auto1["optimal"] is False and not auto1["unplaced_item_ids"]
    candidate = auto1["placements"]
    overlap = [dict(candidate[0]), dict(candidate[1])]; overlap[1]["x_mm"] = overlap[0]["x_mm"]; overlap[1]["y_mm"] = overlap[0]["y_mm"]
    expect("loading_plan_overlap", lambda: validate_plan(db, trip, overlap))
    boundary = [dict(candidate[0])]; boundary[0]["x_mm"] = vehicle.internal_length_mm
    expect("loading_plan_out_of_bounds", lambda: validate_plan(db, trip, boundary))
    duplicate = [dict(candidate[0]), {**candidate[0], "loading_sequence": 99}]
    expect("loading_plan_duplicate_item", lambda: validate_plan(db, trip, duplicate))
    missing_item = items[0]; old_dims = (missing_item.length_mm, missing_item.width_mm, missing_item.height_mm)
    missing_item.length_mm = missing_item.width_mm = missing_item.height_mm = None; db.flush()
    missing_candidate = next(dict(row) for row in candidate if row["shipment_item_id"] == missing_item.id)
    expect("shipment_dimensions_missing", lambda: validate_plan(db, trip, [missing_candidate]))
    missing_item.length_mm, missing_item.width_mm, missing_item.height_mm = old_dims; db.flush()
    missing_item.height_mm = vehicle.internal_height_mm + 1; db.flush()
    expect("loading_plan_height_exceeded", lambda: validate_plan(db, trip, [missing_candidate]))
    missing_item.height_mm = old_dims[2]; db.flush()
    old_payload = vehicle.max_payload_kg; vehicle.max_payload_kg = 100; db.flush()
    expect("vehicle_payload_exceeded", lambda: validate_plan(db, trip, candidate))
    vehicle.max_payload_kg = old_payload; db.flush()
    totals = save_plan(db, trip.id, candidate, "planner"); db.commit()
    assert totals["package_count"] == 4 and totals["product_quantity"] == 17
    assert totals["unknown_weight_item_count"] == 1 and totals["weight_calculation_complete"] is False
    saved_rows = sorted(trip.loading_plan, key=lambda row: row.loading_sequence)
    swap = [{"shipment_item_id": row.shipment_item_id, "x_mm": row.x_mm, "y_mm": row.y_mm,
             "rotation": row.rotation, "loading_sequence": row.loading_sequence,
             "expected_version": row.version} for row in saved_rows]
    swap[0]["loading_sequence"], swap[1]["loading_sequence"] = swap[1]["loading_sequence"], swap[0]["loading_sequence"]
    save_plan(db, trip.id, swap, "planner"); db.commit()
    expect("loading_plan_version_conflict", lambda: save_plan(db, trip.id, swap, "stale-planner"))
    db.rollback()

    trip = transition_trip(db, trip, "planned", trip.version, "planner")
    trip = transition_trip(db, trip, "loading", trip.version, "planner"); db.commit()
    expect("required_evidence_missing", lambda: confirm_loading(
        db, trip.id, acknowledge_unknown_weight=True, idempotency_key="load-required-evidence", actor="loader"))
    db.rollback(); trip = db.get(type(trip), trip.id); trip.evidence_policy = "optional"; db.commit()
    expect("unknown_weight_acknowledgement_required", lambda: confirm_loading(
        db, trip.id, acknowledge_unknown_weight=False, idempotency_key="load-no-ack-0001", actor="loader"))
    db.rollback()
    loaded = confirm_loading(db, trip.id, acknowledge_unknown_weight=True,
                             idempotency_key="load-confirm-0001", actor="loader"); db.commit()
    loaded_retry = confirm_loading(db, trip.id, acknowledge_unknown_weight=True,
                                   idempotency_key="load-confirm-0001", actor="loader")
    assert loaded_retry["idempotent"] is True and loaded["status"] == "loaded"
    expect("idempotency_key_conflict", lambda: confirm_loading(
        db, trip.id, acknowledge_unknown_weight=False, idempotency_key="load-confirm-0001", actor="loader"))

    tracking, tracking_token = start_session(db, trip.id, driver, "phase5-shipment-session"); db.commit()
    pre_dispatch = {"client_point_id": "phase5-pre-dispatch", "latitude": 41.0, "longitude": 69.0,
                    "accuracy_m": 8, "speed_kmh": 0, "heading_deg": 0, "battery_level": 80,
                    "captured_at": datetime.utcnow(), "was_queued": False}
    append_locations(db, tracking.id, driver, tracking_token, [pre_dispatch]); db.commit()
    assert db.get(type(trip), trip.id).status == "loaded"

    dispatched = final_dispatch(db, trip.id, idempotency_key="dispatch-final-0001", actor="dispatcher"); db.commit()
    assert dispatched["status"] == "dispatched" and project.status == "shipped"
    assert dispatched["tracking_session_id"] == tracking.id and dispatched["tracking_start_required"] is False
    assert final_dispatch(db, trip.id, idempotency_key="dispatch-final-0001", actor="dispatcher")["idempotent"] is True
    tracking_retry, tracking_token = start_session(db, trip.id, driver, "phase5-shipment-session"); db.commit()
    assert tracking_retry.id == tracking.id and db.query(MesTripTrackingSession).filter_by(trip_id=trip.id).count() == 1
    departure = datetime.fromisoformat(dispatched["actual_departure_at"])
    stale = {**pre_dispatch, "client_point_id": "phase5-stale", "captured_at": departure-timedelta(seconds=1)}
    append_locations(db, tracking.id, driver, tracking_token, [stale]); db.commit()
    assert db.get(type(trip), trip.id).status == "dispatched"
    moving = {**pre_dispatch, "client_point_id": "phase5-moving", "captured_at": datetime.utcnow()+timedelta(seconds=1), "speed_kmh": 18}
    append_locations(db, tracking.id, driver, tracking_token, [moving]); db.commit()
    trip = db.get(type(trip), trip.id); assert trip.status == "in_transit"
    arrival_version = trip.version
    arrival = confirm_arrival(db, trip.id, expected_version=arrival_version,
                              idempotency_key="phase5-arrival", actor=driver.username); db.commit()
    assert arrival["status"] == "arrived"
    assert confirm_arrival(db, trip.id, expected_version=arrival_version,
                           idempotency_key="phase5-arrival", actor=driver.username)["idempotent"] is True
    trip = db.get(type(trip), trip.id)
    save_trip_evidence(db, trip=trip, evidence_type="arrival", content=b"\x89PNG\r\n\x1a\nphase5-safe-evidence",
                       original_filename="phase5-arrival.png", claimed_mime="image/png", note="TEST arrival",
                       latitude=None, longitude=None, actor=driver.username); db.commit()

    items = db.query(MesShipmentItem).filter_by(trip_id=trip.id).order_by(MesShipmentItem.id).all()
    dispositions = []
    exception_ids = []
    for item in items:
        if item.template.code == "Z1": accepted, damaged, missing = item.loaded_quantity, 0, 0
        elif item.template.code == "Z5" and not exception_ids: accepted, damaged, missing = item.loaded_quantity - 1, 1, 0; exception_ids.append(item.id)
        elif item.template.code == "Z8": accepted, damaged, missing = item.loaded_quantity - 2, 0, 2; exception_ids.append(item.id)
        else: accepted, damaged, missing = item.loaded_quantity, 0, 0
        dispositions.append({"item_id": item.id, "delivered_quantity": item.loaded_quantity,
                             "accepted_quantity": accepted, "damaged_quantity": damaged,
                             "missing_quantity": missing, "notes": "counted"})
    bad = [dict(dispositions[0])]; bad[0]["accepted_quantity"] -= 1
    expect("delivery_balance_invalid", lambda: record_delivery(
        db, trip.id, bad, idempotency_key="delivery-bad-0001", actor="driver"))
    db.rollback()
    delivery = record_delivery(db, trip.id, dispositions, idempotency_key="delivery-final-0001", actor="driver"); db.commit()
    assert delivery["status"] == "delivered" and project.status == "delivered"
    assert project.status != "completed"
    assert all(line.accepted_quantity == 0 for line in project.lines)
    accepted_result = accept_delivery(db, trip.id, recipient_name="Atlas Receiver", notes="accepted with authorized shortage",
                                      resolved_shortage_item_ids=exception_ids,
                                      idempotency_key="accept-final-0001", actor="receiver")
    db.commit(); assert accepted_result["project_status"] == "completed" and project.status == "completed"
    # accepted_quantity is customer-confirmed quantity, not a package count and
    # need not equal ordered quantity when each damaged/missing shortfall is
    # explicitly resolved during trip-level acceptance.
    assert [line.accepted_quantity for line in project.lines] == [2, 4, 8]
    assert [line.damaged_quantity for line in project.lines] == [0, 1, 0]
    assert [line.missing_quantity for line in project.lines] == [0, 0, 2]
    assert sum(line.accepted_quantity for line in project.lines) == 14
    assert sum(line.accepted_quantity + line.damaged_quantity + line.missing_quantity for line in project.lines) == 17
    assert dispatch.status == "accepted"
    assert accept_delivery(db, trip.id, recipient_name="Atlas Receiver", notes="accepted with authorized shortage",
                           resolved_shortage_item_ids=exception_ids,
                           idempotency_key="accept-final-0001", actor="receiver")["idempotent"] is True

    assert db.query(MesInventoryMovement).filter_by(movement_type="trip_load").count() == 4
    assert db.query(MesInventoryMovement).filter_by(movement_type="trip_dispatch").count() == 4
    assert db.query(MesInventoryMovement).filter_by(movement_type="trip_delivery").count() == 4
    assert db.query(MesTripCommand).filter_by(trip_id=trip.id).count() == 9  # 4 assignments + load + dispatch + arrival + delivery + acceptance
    assert db.query(MesTripEvidence).filter_by(trip_id=trip.id).count() == 1
    assert db.query(MesTripLocation).filter_by(trip_id=trip.id).count() == 3
    assert db.get(MesTripLatestLocation, trip.id) is not None
    operation_types = {row.operation_type for row in db.query(ProjectProductionOperation).filter_by(project_id=project.id).all()}
    assert {"trip_loaded", "trip_dispatched", "trip_delivered", "trip_accepted"} <= operation_types, operation_types

    client = TestClient(app)
    admin_token = client.post("/auth/login", json={"username": "ship-admin", "password": "Ship123!"}).json()["access_token"]
    denied_token = client.post("/auth/login", json={"username": "ship-denied", "password": "Denied123!"}).json()["access_token"]
    assert client.get(f"/mes/finished-logistics/trips/{trip.id}/progress",
                      headers={"Authorization": f"Bearer {denied_token}"}).status_code == 403
    progress_response = client.get(f"/mes/finished-logistics/trips/{trip.id}/progress",
                                   headers={"Authorization": f"Bearer {admin_token}"})
    assert progress_response.status_code == 200
    assert {row["kind"] for row in progress_response.json()["history"]} >= {"command", "inventory_movement"}
    db.close()
    print("test_shipment_execution: ALL TESTS PASSED (Z1=2, Z5=5, Z8=10)")


if __name__ == "__main__": main()
