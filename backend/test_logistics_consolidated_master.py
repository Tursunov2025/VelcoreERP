"""Disposable proof for the canonical multi-project logistics composition."""
from __future__ import annotations

import os, sys, tempfile
from pathlib import Path
from types import SimpleNamespace

DB = os.getenv("LOGISTICS_MASTER_E2E_DB") or tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ.update({"DATABASE_URL": f"sqlite:///{DB.replace(chr(92), '/')}", "DB_PATH": DB,
                   "DATABASE_GUARD": "false", "ENVIRONMENT": "test", "JWT_SECRET_KEY": "logistics-master-test"})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import Base, SessionLocal, engine, run_migrations
from models import (MesBomLine, MesFinishedGoodsInventory, MesFinishedGoodsPlacement, MesInventoryMovement,
                    MesJobBomLine, MesJobPackage, MesProductPart, MesProductTemplate, MesProductionJob,
                    MesShipmentItem, MesTrip, MesVehicle, MesWarehouseLocation, ProductionProject,
                    ProductionProjectLine, ProjectLineBomSnapshot, ProjectProductionOperation,
                    ProjectReleaseSnapshot, User)
from services.load_corrections import reload_package, return_to_warehouse, transfer_package, unload_package
from services.finished_logistics import create_trip, transition_trip
from services.shipment_execution import (accept_delivery, automatic_initial_plan, confirm_loading,
    create_consolidated_trip, final_dispatch, record_delivery, save_plan, trip_progress)
from services.trip_documents import document_path, generate_trip_document
from pypdf import PdfReader
from routers.finished_logistics_router import ready_for_logistics


def _vehicle(db, plate):
    row = MesVehicle(vehicle_type="test", registration_number=plate, max_payload_kg=50000,
        internal_length_mm=20000, internal_width_mm=3000, internal_height_mm=3000,
        max_volume_m3=150, operational_state="AVAILABLE", created_by="test", updated_by="test")
    db.add(row); db.flush(); return row


def _ready_project(db, index, template, part, bom, location):
    project = ProductionProject(project_code=f"LM-{index:02d}", project_name=f"Project {index}",
        customer_name_snapshot=f"Customer {index}", destination_city="Toshkent",
        site_name=f"Stop {index}", full_address=f"TEST address {index}", status="released", created_by="test")
    db.add(project); db.flush()
    line = ProductionProjectLine(project_id=project.id, product_id=template.id, quantity=1, status="ready_to_ship")
    db.add(line); db.flush()
    release = ProjectReleaseSnapshot(project_id=project.id, revision=1, source_project_version=1,
        idempotency_key=f"lm-release-{index}", checksum=f"checksum-{index}", released_by="test")
    db.add(release); db.flush()
    snap = ProjectLineBomSnapshot(release_id=release.id, project_line_id=line.id, product_id=template.id,
        source_bom_line_id=bom.id, detail_id=part.id, product_code=template.code, product_name=template.name,
        detail_code=part.part_number, detail_name=part.name, unit="dona", source_quantity=1,
        product_quantity=1, gross_quantity=1)
    db.add(snap); db.flush()
    job = MesProductionJob(job_number=f"LM-JOB-{index:02d}", template_id=template.id, quantity=1,
        status="completed", created_by="test", project_id=project.id, project_line_id=line.id,
        project_release_snapshot_id=release.id)
    db.add(job); db.flush()
    job_line = MesJobBomLine(job_id=job.id, source_bom_line_id=bom.id, part_id=part.id,
        part_number=part.part_number, part_name=part.name, allocated_quantity=1,
        production_required_quantity=1, project_line_bom_snapshot_id=snap.id)
    db.add(job_line); db.flush()
    for kind in ("lazer_completed", "qc_approved", "packaged"):
        db.add(ProjectProductionOperation(project_id=project.id, release_id=release.id,
            project_line_id=line.id, job_id=job.id, job_line_id=job_line.id if kind != "packaged" else None,
            operation_type=kind, result="completed", quantity=1, operator="test", terminal="TEST",
            source_record_type="test", source_record_id=job.id, source_version="1",
            idempotency_key=f"lm-{kind}-{index}"))
    package = MesJobPackage(job_id=job.id, package_number=f"LM-PKG-{index:02d}", quantity=1,
        gross_weight_kg=100, status="placed", location_id=location.id, project_id=project.id,
        project_line_id=line.id, project_release_snapshot_id=release.id)
    db.add(package); db.flush()
    inventory = MesFinishedGoodsInventory(job_id=job.id, package_id=package.id, template_id=template.id,
        product_code=template.code, product_name=template.name, location_id=location.id, quantity=1,
        status="in_stock", created_by="test", project_id=project.id, project_line_id=line.id,
        project_release_snapshot_id=release.id)
    db.add(inventory); db.flush()
    placement = MesFinishedGoodsPlacement(inventory_id=inventory.id, package_id=package.id,
        location_id=location.id, project_id=project.id, project_line_id=line.id, template_id=template.id,
        release_id=release.id, quantity=1, status="placed", placed_by="test", updated_by="test")
    db.add(placement); db.flush(); return project, placement


def test_ten_projects_one_trip_corrections_and_per_project_acceptance():
    Base.metadata.create_all(engine); run_migrations(); db = SessionLocal()
    driver = User(username="lm-driver", password_hash="test", role="driver", department="Logistika")
    driver2 = User(username="lm-driver-2", password_hash="test", role="driver", department="Logistika")
    admin = User(username="lm-admin", password_hash="test", role="admin", department="Admin")
    part = MesProductPart(part_number="LM-DETAIL", name="Detail", created_by="test")
    template = MesProductTemplate(code="LM-PRODUCT", name="Product", length_mm=1000,
        width_mm=500, height_mm=500, weight_kg=100, created_by="test")
    location = MesWarehouseLocation(code="LM-FG", segment_code="LM-FG", location_type="bin", created_by="test")
    db.add_all([driver, driver2, admin, part, template, location]); db.flush()
    bom = MesBomLine(template_id=template.id, part_id=part.id, required_quantity=1, unit="dona")
    db.add(bom); db.flush()
    projects_and_placements = [_ready_project(db, i, template, part, bom, location) for i in range(1, 11)]
    vehicle_a, vehicle_b = _vehicle(db, "LM-A"), _vehicle(db, "LM-B"); db.commit()
    inbox = ready_for_logistics(db=db, user=admin)
    assert inbox["totals"]["project_count"] == 10 and inbox["totals"]["package_count"] == 10
    payload = SimpleNamespace(trip_number="LM-CONSOLIDATED", vehicle_id=vehicle_a.id, driver_user_id=driver.id,
        placement_ids=[p.id for _, p in projects_and_placements], planned_loading_at=None,
        planned_departure_at=None, delivery_deadline_at=None, notes="", evidence_policy="optional",
        completeness_required=False, idempotency_key="lm-consolidated-create")
    created = create_consolidated_trip(db, payload, "planner"); db.commit()
    retry = create_consolidated_trip(db, payload, "planner")
    assert created["project_count"] == 10 and created["package_count"] == 10 and retry["idempotent"]
    trip_a = db.get(MesTrip, created["trip_id"])
    assert len({row.project_id for row in db.query(MesShipmentItem).filter_by(trip_id=trip_a.id).all()}) == 10
    transition_trip(db, trip_a, "loading", trip_a.version, "loader")
    plan = automatic_initial_plan(db, trip_a); save_plan(db, trip_a.id, plan["placements"], "loader")
    confirm_loading(db, trip_a.id, acknowledge_unknown_weight=False, idempotency_key="lm-load-a", actor="loader"); db.commit()
    item = db.query(MesShipmentItem).filter_by(trip_id=trip_a.id, assignment_status="active").first(); db.refresh(trip_a)
    unloaded = unload_package(db, trip_a.id, item.id, expected_trip_version=trip_a.version,
        expected_item_version=item.version, reason="wrong_package", notes="test", idempotency_key="lm-unload", actor="loader"); db.commit()
    item = db.get(MesShipmentItem, item.id); trip_a = db.get(MesTrip, trip_a.id)
    returned = return_to_warehouse(db, trip_a.id, item.id, expected_trip_version=trip_a.version,
        expected_item_version=item.version, reason="wrong_package", notes="test", idempotency_key="lm-return", actor="loader"); db.commit()
    assert returned["available_to_ship"] and item.placement.status == "placed"
    item = db.get(MesShipmentItem, item.id); trip_a = db.get(MesTrip, trip_a.id)
    reload_package(db, trip_a.id, item.id, expected_trip_version=trip_a.version, expected_item_version=item.version,
        reason="wrong_package", notes="test", idempotency_key="lm-reload", actor="loader"); db.commit()
    # A second trip receives a loaded package and then sends it back, preserving both historical rows.
    anchor_project, anchor_placement = projects_and_placements[0]
    trip_b = create_trip(db, SimpleNamespace(trip_number="LM-TRANSFER", vehicle_id=vehicle_b.id,
        driver_user_id=driver2.id, project_id=anchor_project.id, release_id=anchor_placement.release_id,
        destination_city=anchor_project.destination_city, destination_site=anchor_project.site_name,
        destination_address=anchor_project.full_address, planned_loading_at=None, planned_departure_at=None,
        delivery_deadline_at=None, notes="", evidence_policy="optional", completeness_required=False), "planner")
    transition_trip(db, trip_b, "planned", trip_b.version, "planner"); db.commit()
    item = db.query(MesShipmentItem).filter_by(trip_id=trip_a.id, assignment_status="active").first(); trip_a=db.get(MesTrip,trip_a.id); trip_b=db.get(MesTrip,trip_b.id)
    source_version, target_version, item_version = trip_a.version, trip_b.version, item.version
    moved = transfer_package(db, trip_a.id, item.id, target_trip_id=trip_b.id,
        expected_trip_version=source_version, expected_target_trip_version=target_version,
        expected_item_version=item_version, reason="wrong_truck", notes="test",
        idempotency_key="lm-transfer", actor="loader"); db.commit()
    assert db.query(MesShipmentItem).filter_by(package_id=item.package_id, assignment_status="active").count() == 1
    assert transfer_package(db, trip_a.id, item.id, target_trip_id=trip_b.id,
        expected_trip_version=source_version, expected_target_trip_version=target_version,
        expected_item_version=item_version, reason="wrong_truck", notes="test",
        idempotency_key="lm-transfer", actor="loader")["idempotent"]
    # Load through the canonical writer, then unload/return through correction services.
    trip_b=db.get(MesTrip,trip_b.id); transition_trip(db,trip_b,"loading",trip_b.version,"loader")
    plan_b=automatic_initial_plan(db,trip_b); save_plan(db,trip_b.id,plan_b["placements"],"loader")
    confirm_loading(db,trip_b.id,acknowledge_unknown_weight=False,idempotency_key="lm-load-b",actor="loader"); db.commit()
    target_item = db.get(MesShipmentItem, moved["target_item"]["id"]); trip_b=db.get(MesTrip,trip_b.id)
    unload_package(db,trip_b.id,target_item.id,expected_trip_version=trip_b.version,
        expected_item_version=target_item.version,reason="wrong_truck",notes="test",
        idempotency_key="lm-transfer-unload",actor="loader"); db.commit()
    target_item=db.get(MesShipmentItem,target_item.id); trip_b=db.get(MesTrip,trip_b.id)
    return_to_warehouse(db, trip_b.id, target_item.id, expected_trip_version=trip_b.version,
        expected_item_version=target_item.version, reason="wrong_truck", notes="test",
        idempotency_key="lm-transfer-return", actor="loader"); db.commit()
    trip_a=db.get(MesTrip,trip_a.id)
    confirm_loading(db,trip_a.id,acknowledge_unknown_weight=False,idempotency_key="lm-load-a-final",actor="loader"); db.commit()
    before_dispatch=db.query(MesInventoryMovement).filter_by(movement_type="trip_load").count()
    final_dispatch(db,trip_a.id,idempotency_key="lm-dispatch",actor="dispatcher"); db.commit()
    assert db.query(MesInventoryMovement).filter_by(movement_type="trip_load").count()==before_dispatch
    trip_a=db.get(MesTrip,trip_a.id); transition_trip(db,trip_a,"in_transit",trip_a.version,"gps"); db.commit()
    items=db.query(MesShipmentItem).filter_by(trip_id=trip_a.id,assignment_status="active").all()
    for n, project_id in enumerate(sorted({x.project_id for x in items}),1):
        subset=[x for x in items if x.project_id==project_id]
        result=record_delivery(db,trip_a.id,[{"item_id":x.id,"delivered_quantity":x.loaded_quantity,
            "accepted_quantity":x.loaded_quantity,"damaged_quantity":0,"missing_quantity":0,"notes":""} for x in subset],
            idempotency_key=f"lm-delivery-{n}",actor="driver"); db.commit()
        accepted=accept_delivery(db,trip_a.id,recipient_name="TEST",notes="",resolved_shortage_item_ids=[],
            idempotency_key=f"lm-accept-{n}",actor="receiver",project_id=project_id); db.commit()
        if n < 9: assert accepted["trip_complete"] is False and accepted["status"] != "accepted"
    assert db.get(MesTrip,trip_a.id).status == "accepted"
    assert trip_progress(db,db.get(MesTrip,trip_a.id))["project_count"] == 9
    documents = [generate_trip_document(db, trip_a.id, kind, "planner", "uz") for kind in
                 ("packing_list", "loading_list", "trip_manifest", "delivery_note")]
    db.commit()
    assert all(row.file_size > 1000 and len(PdfReader(str(document_path(row))).pages) >= 1 for row in documents)
    assert generate_trip_document(db, trip_a.id, "trip_manifest", "planner", "uz").id == documents[2].id
    db.close()
