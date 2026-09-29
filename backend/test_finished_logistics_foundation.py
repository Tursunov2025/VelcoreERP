"""Checkpoint B foundation acceptance tests on an isolated SQLite database."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
ROOT = Path(tempfile.mkdtemp(prefix="velcore-finished-logistics-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB.replace(chr(92), '/')}", "DB_PATH": DB,
    "DATA_ROOT": str(ROOT), "DATABASE_GUARD": "false", "ENVIRONMENT": "test",
    "JWT_SECRET_KEY": "finished-logistics-test-secret",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402

from auth.security import hash_password  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    MesDispatch, MesFinishedGoodsInventory, MesFinishedGoodsPlacement, MesInventoryMovement,
    MesJobPackage, MesJobRouteStep, MesProductionJob, MesProductionStage, MesProductTemplate,
    MesTripEvidence, MesVehicle, ProductionProject, ProductionProjectLine,
    ProjectReleaseSnapshot, User,
)
from services.finished_logistics import (  # noqa: E402
    LogisticsError, attach_dispatch, create_location_node, create_trip, create_vehicle,
    save_trip_evidence, transition_trip,
)
from services.mes_warehouse_terminal import (  # noqa: E402
    assign_package_to_location, create_location, warehouse_stage_ids,
)


def expect(code: str, fn) -> None:
    try:
        fn()
        raise AssertionError(f"Expected {code}")
    except LogisticsError as exc:
        assert exc.code == code, (exc.code, code)


def main() -> None:
    Base.metadata.create_all(engine); run_migrations(); run_migrations(); db = SessionLocal()
    admin = User(username="checkpoint-b-admin", password_hash=hash_password("CheckpointB123!"), role="admin", department="Admin")
    denied = User(username="checkpoint-b-denied", password_hash=hash_password("Denied123!"), role="operator", department="Kesish")
    template = MesProductTemplate(code="B-PRODUCT", name="B Product", created_by="test")
    project = ProductionProject(project_code="B-PROJECT", project_name="B Project", customer_name_snapshot="Customer",
                                destination_city="Toshkent", site_name="Atlas", full_address="Toshkent, Atlas",
                                status="released", release_revision=1, created_by="test")
    db.add_all([admin, denied, template, project]); db.flush()
    line = ProductionProjectLine(project_id=project.id, product_id=template.id, quantity=4, status="released")
    release = ProjectReleaseSnapshot(project_id=project.id, revision=1, source_project_version=1,
                                     idempotency_key="checkpoint-b-release", checksum="0" * 64, released_by="test")
    stage = MesProductionStage(name="Sklad", department="Ombor", is_active=True)
    db.add_all([line, release, stage]); db.flush()
    job = MesProductionJob(job_number="B-JOB", customer_name="Customer", template_id=template.id, quantity=4,
                           status="in_progress", created_by="test", project_id=project.id,
                           project_line_id=line.id, project_release_snapshot_id=release.id)
    db.add(job); db.flush()
    db.add(MesJobRouteStep(job_id=job.id, stage_id=stage.id, stage_name="Sklad", step_order=1,
                           department="Ombor", accepted_at=stage.created_at, started_at=stage.created_at))
    package = MesJobPackage(job_id=job.id, package_number="B-PKG-1", quantity=2, status="received",
                            project_id=project.id, project_line_id=line.id, project_release_snapshot_id=release.id)
    db.add(package); db.commit()

    # Normalized hierarchy and deterministic full codes.
    warehouse = create_location_node(db, parent_id=None, location_type="warehouse", segment_code="FG", description="Finished", actor="test")
    zone = create_location_node(db, parent_id=warehouse.id, location_type="zone", segment_code="Z1", description="", actor="test")
    aisle = create_location_node(db, parent_id=zone.id, location_type="aisle", segment_code="A01", description="", actor="test")
    rack = create_location_node(db, parent_id=aisle.id, location_type="rack", segment_code="R01", description="", actor="test")
    bin_location = create_location_node(db, parent_id=rack.id, location_type="bin", segment_code="B01", description="", actor="test")
    assert bin_location.code == "FG/Z1/A01/R01/B01"
    db.commit()
    expect("location_code_exists", lambda: create_location_node(db, parent_id=rack.id, location_type="bin", segment_code="B01", description="", actor="test"))
    db.rollback()
    # Legacy flat locations remain supported.
    legacy = create_location(db, "test", "A-01-01")
    assert legacy["code"] == "A-01-01"
    db.commit()

    # Inactive location and traceability mismatch reject before any mutation.
    inactive = create_location_node(db, parent_id=rack.id, location_type="bin", segment_code="OFF", description="", actor="test")
    inactive.is_active = False; db.commit()
    try:
        assign_package_to_location(db, job, warehouse_stage_ids(db), "test", package_id=package.id, location_id=inactive.id)
        raise AssertionError("inactive location accepted")
    except ValueError as exc:
        assert "not found" in str(exc).lower()
        db.rollback()

    package.project_release_snapshot_id = None; db.commit()
    try:
        assign_package_to_location(db, job, warehouse_stage_ids(db), "test", package_id=package.id, location_id=bin_location.id)
        raise AssertionError("release mismatch accepted")
    except ValueError as exc:
        assert "does not match" in str(exc)
        db.rollback()
    package = db.get(MesJobPackage, package.id); package.project_release_snapshot_id = release.id; db.commit()

    inventory = assign_package_to_location(db, job, warehouse_stage_ids(db), "warehouse", package_id=package.id, location_id=bin_location.id)
    db.commit()
    placement = db.query(MesFinishedGoodsPlacement).filter_by(inventory_id=inventory.id).one()
    assert placement.quantity == 2 and placement.project_id == project.id and placement.release_id == release.id
    assert db.query(MesInventoryMovement).filter_by(inventory_id=inventory.id, movement_type="placement").count() == 1
    try:
        assign_package_to_location(db, job, warehouse_stage_ids(db), "warehouse", package_id=package.id, location_id=bin_location.id)
        raise AssertionError("duplicate placement accepted")
    except ValueError:
        db.rollback()

    over = MesJobPackage(job_id=job.id, package_number="B-PKG-OVER", quantity=3, status="received",
                         project_id=project.id, project_line_id=line.id, project_release_snapshot_id=release.id)
    db.add(over); db.commit(); movement_count = db.query(MesInventoryMovement).count()
    try:
        assign_package_to_location(db, job, warehouse_stage_ids(db), "warehouse", package_id=over.id, location_id=bin_location.id)
        raise AssertionError("over-placement accepted")
    except ValueError as exc:
        assert "exceeds eligible" in str(exc)
        db.rollback()
    assert db.query(MesFinishedGoodsInventory).filter_by(package_id=over.id).count() == 0
    assert db.query(MesInventoryMovement).count() == movement_count
    assert db.get(MesJobPackage, over.id).location_id is None

    vehicle_data = SimpleNamespace(vehicle_type="truck", registration_number="01 A 001 AA", driver_name="Driver",
                                   driver_phone="+998900000000", max_payload_kg=12000,
                                   internal_length_mm=13600, internal_width_mm=2450, internal_height_mm=2700,
                                   max_volume_m3=89, is_active=True)
    vehicle = create_vehicle(db, vehicle_data, "dispatcher"); db.commit()
    assert vehicle.registration_number == "01A001AA"
    expect("vehicle_registration_exists", lambda: create_vehicle(db, vehicle_data, "dispatcher")); db.rollback()
    invalid_vehicle = SimpleNamespace(**vars(vehicle_data)); invalid_vehicle.max_payload_kg = 0
    expect("invalid_vehicle_measurement", lambda: create_vehicle(db, invalid_vehicle, "dispatcher"))

    trip_data = SimpleNamespace(trip_number="TRIP-B-1", vehicle_id=vehicle.id, project_id=project.id,
                                release_id=release.id, destination_city="Toshkent", destination_site="Atlas",
                                destination_address="Toshkent, Atlas", planned_departure_at=None, notes="")
    trip = create_trip(db, trip_data, "dispatcher"); db.commit()
    wrong_destination = SimpleNamespace(**vars(trip_data)); wrong_destination.trip_number = "TRIP-B-2"; wrong_destination.destination_site = "Other"
    expect("trip_destination_mismatch", lambda: create_trip(db, wrong_destination, "dispatcher"))
    expect("invalid_trip_transition", lambda: transition_trip(db, trip, "delivered", trip.version, "dispatcher"))

    dispatch = MesDispatch(dispatch_number="B-DISPATCH", job_id=job.id, project_id=project.id,
                           customer_name="Customer", destination_city="Toshkent", site_name="Atlas",
                           status="pending", created_by="test")
    db.add(dispatch); db.commit(); attach_dispatch(db, trip, dispatch.id, "dispatcher"); db.commit()
    assert dispatch.trip_id == trip.id

    png = b"\x89PNG\r\n\x1a\n" + b"safe-checkpoint-b"
    evidence = save_trip_evidence(db, trip=trip, evidence_type="arrival", content=png,
                                  original_filename="arrival.png", claimed_mime="image/png", actor="dispatcher")
    db.commit()
    assert evidence.checksum == hashlib.sha256(png).hexdigest()
    assert not Path(evidence.storage_relative_path).is_absolute()
    for name, content, mime, expected in (
        ("bad.svg", b"<svg><script/></svg>", "image/svg+xml", "unsafe_evidence_type"),
        ("bad.js", b"alert(1)", "application/javascript", "unsafe_evidence_type"),
        ("../escape.png", png, "image/png", "unsafe_filename"),
        ("scripted.pdf", b"%PDF-1.7 /JavaScript", "application/pdf", "unsafe_evidence_type"),
    ):
        expect(expected, lambda n=name, c=content, m=mime: save_trip_evidence(
            db, trip=trip, evidence_type="arrival", content=c, original_filename=n,
            claimed_mime=m, actor="dispatcher"))
    from services.finished_logistics import MAX_EVIDENCE_BYTES
    expect("evidence_size_invalid", lambda: save_trip_evidence(
        db, trip=trip, evidence_type="arrival", content=b"x" * (MAX_EVIDENCE_BYTES + 1),
        original_filename="large.png", claimed_mime="image/png", actor="dispatcher"))

    client = TestClient(app)
    admin_token = client.post("/auth/login", json={"username": "checkpoint-b-admin", "password": "CheckpointB123!"}).json()["access_token"]
    denied_token = client.post("/auth/login", json={"username": "checkpoint-b-denied", "password": "Denied123!"}).json()["access_token"]
    assert client.get(f"/mes/finished-logistics/evidence/{evidence.id}/download",
                      headers={"Authorization": f"Bearer {denied_token}"}).status_code == 403
    downloaded = client.get(f"/mes/finished-logistics/evidence/{evidence.id}/download",
                            headers={"Authorization": f"Bearer {admin_token}"})
    assert downloaded.status_code == 200 and downloaded.content == png
    assert db.query(MesTripEvidence).count() == 1
    db.close()
    print("test_finished_logistics_foundation: ALL TESTS PASSED")


if __name__ == "__main__": main()
