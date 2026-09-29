"""Phase 4 full mutation lifecycle through the canonical HTTP APIs on disposable SQLite."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
ROOT = Path(tempfile.mkdtemp(prefix="velcore-phase4-mutation-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB.replace(chr(92), '/')}", "DB_PATH": DB,
    "DATA_ROOT": str(ROOT), "DATABASE_GUARD": "false", "ENVIRONMENT": "test",
    "JWT_SECRET_KEY": "phase4-mutation-secret",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402
from auth.security import hash_password  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    AuditLog, MesBomLine, MesFinishedGoodsInventory, MesFinishedGoodsPlacement,
    MesInventoryMovement, MesJobPackage, MesProductPart, MesProductTemplate,
    MesProductionJob, MesProductionRoute, MesProductionStage, MesRouteStep, MesShipmentItem, MesTrip,
    MesTripCommand, MesTripEvidence, MesTripLatestLocation, MesTripLocation,
    MesTripTrackingSession, MesVehicle, MesWarehouseLocation, ProductionProject,
    ProductionProjectLine, User, UserPermission,
)
from services.logistics_planning import sla_state  # noqa: E402
from services.production_projects import release_project  # noqa: E402
from services.project_execution import record_absolute_operation  # noqa: E402


def ok(response, status=200):
    assert response.status_code == status, (response.status_code, response.text)
    return response.json()


def auth(client, username, password):
    token = ok(client.post("/auth/login", json={"username": username, "password": password}))["access_token"]
    return {"Authorization": f"Bearer {token}"}


def setup_module():
    Base.metadata.create_all(engine)
    run_migrations(); run_migrations()


def teardown_module():
    engine.dispose()
    Path(DB).unlink(missing_ok=True)
    shutil.rmtree(ROOT, ignore_errors=True)


def test_full_phase4_mutation_lifecycle():
    db = SessionLocal()
    admin = User(username="phase4-admin", password_hash=hash_password("Admin123!"), role="admin", department="Admin")
    driver = User(username="phase4-driver", password_hash=hash_password("Driver123!"), role="driver", department="Logistika")
    other = User(username="phase4-other", password_hash=hash_password("Other123!"), role="driver", department="Logistika")
    db.add_all([admin, driver, other]); db.flush()
    db.add_all([UserPermission(user_id=driver.id, module="gps_trip_track", enabled=True),
                UserPermission(user_id=other.id, module="gps_trip_track", enabled=True)])
    stage = MesProductionStage(name="P4-LAZER", department="Kesish", is_active=True)
    product = MesProductTemplate(code="P4-Z1", name="Phase 4 product", length_mm=1000,
                                 width_mm=500, height_mm=500, weight_kg=25, created_by="test")
    part = MesProductPart(part_number="P4-DETAIL", name="Phase 4 detail", created_by="test")
    db.add_all([stage, product, part]); db.flush()
    route = MesProductionRoute(template_id=product.id, name="P4 route", version=1, is_default=True, created_by="test")
    db.add(route); db.flush(); product.default_route_id = route.id
    db.add_all([MesRouteStep(route_id=route.id, stage_id=stage.id, step_order=1, department="Kesish"),
                MesBomLine(template_id=product.id, part_id=part.id, required_quantity=1, unit="dona")])
    project = ProductionProject(project_code="P4-E2E", project_name="Phase 4 lifecycle",
                                customer_name_snapshot="TEST", destination_city="Toshkent",
                                site_name="Atlas", full_address="TEST Atlas", status="planned", created_by="test")
    db.add(project); db.flush()
    db.add(ProductionProjectLine(project_id=project.id, product_id=product.id, quantity=2, status="planned")); db.commit()
    project, release, _ = release_project(db, project.id, project.version, "phase4-release", "phase4-admin"); db.commit()
    job = db.query(MesProductionJob).filter_by(project_id=project.id).one()
    record_absolute_operation(db, job, operation_type="lazer_completed", absolute_quantity=2,
                              username="fixture", terminal="LAZER", job_line=job.bom_lines[0])
    record_absolute_operation(db, job, operation_type="qc_approved", absolute_quantity=2,
                              username="fixture", terminal="QC", job_line=job.bom_lines[0])
    location = MesWarehouseLocation(code="P4-FG", segment_code="P4-FG", location_type="warehouse", is_active=True, created_by="fixture")
    db.add(location); db.flush()
    package = MesJobPackage(job_id=job.id, package_number="P4-PKG", quantity=2, gross_weight_kg=50,
                            status="placed", location_id=location.id, project_id=project.id,
                            project_line_id=job.project_line_id, project_release_snapshot_id=release.id)
    db.add(package); db.flush()
    record_absolute_operation(db, job, operation_type="packaged", absolute_quantity=2,
                              username="fixture", terminal="PACKAGING")
    inventory = MesFinishedGoodsInventory(job_id=job.id, package_id=package.id, template_id=product.id,
                                          product_code=product.code, product_name=product.name, location_id=location.id,
                                          quantity=2, status="in_stock", created_by="fixture", project_id=project.id,
                                          project_line_id=job.project_line_id, project_release_snapshot_id=release.id)
    db.add(inventory); db.flush()
    placement = MesFinishedGoodsPlacement(inventory_id=inventory.id, package_id=package.id, location_id=location.id,
                                          project_id=project.id, project_line_id=job.project_line_id,
                                          template_id=product.id, release_id=release.id, quantity=2,
                                          status="placed", placed_by="fixture", updated_by="fixture")
    vehicle = MesVehicle(vehicle_type="truck", registration_number="P4-AVAILABLE", max_payload_kg=1000,
                         internal_length_mm=4000, internal_width_mm=2000, internal_height_mm=2000,
                         operational_state="AVAILABLE", is_active=True, created_by="fixture", updated_by="fixture")
    db.add_all([placement, vehicle]); db.flush()
    trip = MesTrip(trip_number="P4-MUTATION-TRIP", vehicle_id=None, driver_user_id=None,
                   project_id=project.id, release_id=release.id, destination_city="Toshkent",
                   destination_site="Atlas", destination_address="TEST Atlas", status="planned",
                   evidence_policy="optional", completeness_required=True, created_by="fixture", updated_by="fixture")
    db.add(trip); db.commit(); trip_id, vehicle_id, placement_id, driver_id = trip.id, vehicle.id, placement.id, driver.id
    db.close()

    client = TestClient(app)
    admin_h = auth(client, "phase4-admin", "Admin123!")
    driver_h = auth(client, "phase4-driver", "Driver123!")
    other_h = auth(client, "phase4-other", "Other123!")

    current = ok(client.get(f"/mes/finished-logistics/trips/{trip_id}", headers=admin_h))
    assert current["status"] == "planned" and current["vehicle_id"] is None
    current = ok(client.put(f"/mes/finished-logistics/trips/{trip_id}/assignment", headers=admin_h,
                            json={"expected_version": current["version"], "vehicle_id": vehicle_id, "driver_user_id": driver_id}))
    now = datetime.utcnow()
    current = ok(client.put(f"/mes/finished-logistics/trips/{trip_id}/planning", headers=admin_h, json={
        "expected_version": current["version"], "planned_loading_at": (now-timedelta(minutes=5)).isoformat(),
        "planned_departure_at": (now+timedelta(minutes=5)).isoformat(),
        "delivery_deadline_at": (now+timedelta(hours=1)).isoformat()}))
    assigned = ok(client.post(f"/mes/finished-logistics/trips/{trip_id}/shipment-items", headers=admin_h,
                              json={"placement_id": placement_id, "idempotency_key": "p4-assign-item"}), 201)
    item_id = assigned["item"]["id"]
    plan = ok(client.post(f"/mes/finished-logistics/trips/{trip_id}/loading-plan/automatic?persist=true", headers=admin_h))
    assert plan["saved_totals"]["package_count"] == 1
    current = ok(client.post(f"/mes/finished-logistics/trips/{trip_id}/transition", headers=admin_h,
                             json={"status": "loading", "expected_version": current["version"]}))
    assert current["status"] == "loading"

    for endpoint, payload in (
        ("assignment", {"expected_version": current["version"], "vehicle_id": vehicle_id, "driver_user_id": driver_id}),
        ("planning", {"expected_version": current["version"], "planned_loading_at": None,
                      "planned_departure_at": None, "delivery_deadline_at": None}),
    ):
        assert client.put(f"/mes/finished-logistics/trips/{trip_id}/{endpoint}", headers=driver_h, json=payload).status_code == 403
    assert client.get(f"/mes/finished-logistics/trips/{trip_id}", headers=other_h).status_code == 403

    load_payload = {"acknowledge_unknown_weight": False, "idempotency_key": "p4-load-once"}
    loaded = ok(client.post(f"/mes/finished-logistics/trips/{trip_id}/confirm-loading", headers=admin_h, json=load_payload))
    loaded_retry = ok(client.post(f"/mes/finished-logistics/trips/{trip_id}/confirm-loading", headers=admin_h, json=load_payload))
    assert loaded["status"] == "loaded" and loaded_retry["idempotent"] is True
    session_payload = {"client_session_id": "p4-session-device"}
    started = ok(client.post(f"/mes/finished-logistics/trips/{trip_id}/tracking/start", headers=driver_h, json=session_payload))
    pre_dispatch_h = {**driver_h, "X-Tracking-Authorization": started["tracking_authorization"]}
    pre_dispatch = {"client_point_id": "p4-pre-dispatch", "latitude": 41.0, "longitude": 69.0,
                    "accuracy_m": 8, "speed_kmh": 0, "captured_at": datetime.utcnow().isoformat(), "was_queued": False}
    ok(client.post(f"/mes/finished-logistics/tracking/sessions/{started['id']}/locations", headers=pre_dispatch_h,
                   json={"points": [pre_dispatch]}))
    assert ok(client.get(f"/mes/finished-logistics/trips/{trip_id}", headers=driver_h))["status"] == "loaded"
    dispatch_payload = {"idempotency_key": "p4-dispatch-once"}
    dispatched = ok(client.post(f"/mes/finished-logistics/trips/{trip_id}/dispatch", headers=admin_h, json=dispatch_payload))
    dispatch_retry = ok(client.post(f"/mes/finished-logistics/trips/{trip_id}/dispatch", headers=admin_h, json=dispatch_payload))
    assert dispatched["status"] == "dispatched" and dispatch_retry["idempotent"] is True
    assert dispatched["tracking_session_id"] == started["id"] and dispatched["tracking_start_required"] is False

    restarted = ok(client.post(f"/mes/finished-logistics/trips/{trip_id}/tracking/start", headers=driver_h, json=session_payload))
    assert started["id"] == restarted["id"]
    tracking_h = {**driver_h, "X-Tracking-Authorization": restarted["tracking_authorization"]}
    departure = datetime.fromisoformat(dispatched["actual_departure_at"])
    stale = {"client_point_id": "p4-stale-point", "latitude": 41.0, "longitude": 69.0,
             "accuracy_m": 8, "speed_kmh": 0, "captured_at": (departure-timedelta(seconds=1)).isoformat(), "was_queued": True}
    ok(client.post(f"/mes/finished-logistics/tracking/sessions/{started['id']}/locations", headers=tracking_h, json={"points": [stale]}))
    assert ok(client.get(f"/mes/finished-logistics/trips/{trip_id}", headers=driver_h))["status"] == "dispatched"
    moving = {**stale, "client_point_id": "p4-moving-point", "captured_at": (datetime.utcnow()+timedelta(seconds=1)).isoformat(), "speed_kmh": 12}
    gps_result = ok(client.post(f"/mes/finished-logistics/tracking/sessions/{started['id']}/locations", headers=tracking_h, json={"points": [moving]}))
    assert gps_result["accepted"] == 1
    current = ok(client.get(f"/mes/finished-logistics/trips/{trip_id}", headers=driver_h))
    assert current["status"] == "in_transit"

    arrival_payload = {"expected_version": current["version"], "idempotency_key": "p4-arrival-once"}
    assert client.post(f"/mes/finished-logistics/trips/{trip_id}/arrival", headers=other_h,
                       json={"expected_version": current["version"], "idempotency_key": "p4-other-arrival"}).status_code == 403
    arrived = ok(client.post(f"/mes/finished-logistics/trips/{trip_id}/arrival", headers=driver_h, json=arrival_payload))
    arrival_retry = ok(client.post(f"/mes/finished-logistics/trips/{trip_id}/arrival", headers=driver_h, json=arrival_payload))
    assert arrived["status"] == "arrived" and arrived["trip_version"] == current["version"] + 1
    assert arrived["arrived_at"] and arrival_retry["idempotent"] is True

    evidence = ok(client.post(f"/mes/finished-logistics/trips/{trip_id}/evidence", headers=driver_h,
                              data={"evidence_type": "arrival", "note": "TEST delivery evidence"},
                              files={"file": ("arrival.png", b"\x89PNG\r\n\x1a\nphase4-safe-evidence", "image/png")}), 201)
    delivery_payload = {"idempotency_key": "p4-delivery-once", "dispositions": [{
        "item_id": item_id, "delivered_quantity": 2, "accepted_quantity": 2,
        "damaged_quantity": 0, "missing_quantity": 0, "notes": "received"}]}
    delivered = ok(client.post(f"/mes/finished-logistics/trips/{trip_id}/delivery", headers=driver_h, json=delivery_payload))
    delivery_retry = ok(client.post(f"/mes/finished-logistics/trips/{trip_id}/delivery", headers=driver_h, json=delivery_payload))
    assert delivered["status"] == "delivered" and delivery_retry["idempotent"] is True
    accepted = ok(client.post(f"/mes/finished-logistics/trips/{trip_id}/acceptance", headers=admin_h, json={
        "recipient_name": "TEST Receiver", "notes": "accepted", "resolved_shortage_item_ids": [],
        "idempotency_key": "p4-accept-once"}))
    assert accepted["status"] == "accepted"
    rollback = client.post(f"/mes/finished-logistics/trips/{trip_id}/transition", headers=admin_h,
                           json={"status": "in_transit", "expected_version": accepted["trip_version"]})
    assert rollback.status_code == 409

    db = SessionLocal(); trip = db.get(MesTrip, trip_id); item = db.get(MesShipmentItem, item_id)
    movements = db.query(MesInventoryMovement).filter_by(inventory_id=item.inventory_id).all()
    movement_counts = {kind: sum(row.movement_type == kind for row in movements)
                       for kind in ("trip_load", "trip_dispatch", "trip_delivery")}
    assert movement_counts == {"trip_load": 1, "trip_dispatch": 1, "trip_delivery": 1}
    assert db.query(MesTripTrackingSession).filter_by(trip_id=trip_id).count() == 1
    assert db.query(MesTripLocation).filter_by(trip_id=trip_id).count() == 3
    assert db.get(MesTripLatestLocation, trip_id) is not None
    assert db.query(MesTripEvidence).filter_by(trip_id=trip_id).count() == 1
    assert trip.status == "accepted" and trip.arrived_at is not None and trip.updated_by == "phase4-admin"
    assert db.query(MesTripCommand).filter_by(trip_id=trip_id, command_type="confirm_arrival").count() == 1
    arrival_audit = db.query(AuditLog).filter_by(entity_type="mes_trip", entity_id=trip_id, action="arrival_confirmed").one()
    assert arrival_audit.username == "phase4-driver"
    assert db.get(MesFinishedGoodsInventory, item.inventory_id).status == "delivered"
    assert sla_state(trip, trip.arrived_at) == "delivered_on_time"
    trip.delivery_deadline_at = None; assert sla_state(trip) == "deadline_unavailable"
    trip.delivery_deadline_at = trip.arrived_at-timedelta(seconds=1); assert sla_state(trip) == "delivered_late"
    trip.status = "in_transit"; trip.arrived_at = None; trip.delivery_deadline_at = datetime.utcnow()-timedelta(seconds=1)
    assert sla_state(trip) == "delayed"; db.rollback()
    project_id, release_id = trip.project_id, trip.release_id
    db.close()
    history = ok(client.get(f"/mes/finished-logistics/trips/{trip_id}/progress", headers=admin_h))["history"]
    types = {row["type"] for row in history}
    assert {"status", "confirm_loading", "dispatch", "gps_tracking_start", "gps_in_transit", "arrival_confirmed", "delivery", "acceptance"} <= types
    vehicle_state = ok(client.get("/mes/finished-logistics/vehicles?include_inactive=true", headers=admin_h))["vehicles"]
    assert next(row for row in vehicle_state if row["id"] == vehicle_id)["operational_state"] == "AVAILABLE"
    db = SessionLocal()
    reusable = MesTrip(trip_number="P4-REUSABLE", vehicle_id=None, driver_user_id=None,
                       project_id=project_id, release_id=release_id, destination_city="Toshkent",
                       destination_site="Atlas", destination_address="TEST Atlas", status="planned",
                       evidence_policy="optional", created_by="fixture", updated_by="fixture")
    db.add(reusable); db.commit(); reusable_id, reusable_version = reusable.id, reusable.version; db.close()
    reused = ok(client.put(f"/mes/finished-logistics/trips/{reusable_id}/assignment", headers=admin_h,
                           json={"expected_version": reusable_version, "vehicle_id": vehicle_id, "driver_user_id": driver_id}))
    assert reused["vehicle_id"] == vehicle_id and reused["driver_user_id"] == driver_id
