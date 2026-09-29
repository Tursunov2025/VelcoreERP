"""Checkpoint B foundation over existing finished inventory and MES dispatch records."""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime
from pathlib import Path, PurePath
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.paths import UPLOAD_PATH
from models import (
    MesDispatch,
    MesFinishedGoodsInventory,
    MesFinishedGoodsPlacement,
    MesTrip,
    MesTripEvidence,
    MesVehicle,
    MesWarehouseLocation,
    ProductionProject,
    ProjectReleaseSnapshot,
    User,
    UserIdentityProfile,
)
from services.audit import log_action, log_value_change
from services.trip_lifecycle import TRIP_TRANSITIONS, TripLifecycleError, require_transition


LOCATION_LEVELS = ("warehouse", "zone", "aisle", "rack", "bin")
IMAGE_EVIDENCE = {
    "loading_start", "loaded_truck", "seal_vehicle", "departure",
    "arrival", "unloading", "acceptance_photo", "loaded_truck_photo",
    "departure_photo", "arrival_photo", "unloading_photo",
}
POD_EVIDENCE = "pod_document"
MAX_EVIDENCE_BYTES = int(os.getenv("TRIP_EVIDENCE_MAX_MB", "15")) * 1024 * 1024


class LogisticsError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _segment(value: str) -> str:
    clean = re.sub(r"[^A-Z0-9_-]+", "-", (value or "").strip().upper()).strip("-")
    if not clean or len(clean) > 64:
        raise LogisticsError("invalid_location_segment", "Location segment is invalid", 422)
    return clean


def create_location_node(db: Session, *, parent_id: int | None, location_type: str,
                         segment_code: str, description: str, actor: str) -> MesWarehouseLocation:
    kind = (location_type or "").strip().lower()
    if kind not in LOCATION_LEVELS:
        raise LogisticsError("invalid_location_type", "Invalid location type", 422)
    segment = _segment(segment_code)
    parent = None
    if parent_id is not None:
        parent = db.query(MesWarehouseLocation).with_for_update().filter_by(id=parent_id).first()
        if not parent:
            raise LogisticsError("location_parent_not_found", "Parent location not found", 404)
        expected = LOCATION_LEVELS[LOCATION_LEVELS.index(parent.location_type or "bin") + 1] if (parent.location_type or "bin") != "bin" else None
        if expected != kind:
            raise LogisticsError("invalid_location_hierarchy", "Location level does not follow its parent")
        code = f"{parent.code}/{segment}"
    else:
        if kind != "warehouse":
            raise LogisticsError("invalid_location_hierarchy", "Only a warehouse may be a root location")
        code = segment
    if db.query(MesWarehouseLocation).filter_by(code=code).first():
        raise LogisticsError("location_code_exists", "Location code already exists")
    node = MesWarehouseLocation(
        code=code, segment_code=segment, location_type=kind, parent_id=parent_id,
        description=(description or "").strip(), is_active=True, created_by=actor,
    )
    db.add(node)
    try:
        db.flush()
    except IntegrityError as exc:
        raise LogisticsError("location_code_exists", "Location code already exists") from exc
    log_action(db, actor, "create", "mes_warehouse_location", node.id, code)
    return node


def placement_totals(db: Session, project_id: int | None = None) -> dict:
    inventory = db.query(MesFinishedGoodsInventory)
    placements = db.query(MesFinishedGoodsPlacement)
    if project_id is not None:
        inventory = inventory.filter(MesFinishedGoodsInventory.project_id == project_id)
        placements = placements.filter(MesFinishedGoodsPlacement.project_id == project_id)
    inventory_rows = inventory.all()
    placement_rows = placements.all()
    total = sum(float(row.quantity or 0) for row in inventory_rows)
    placed = sum(float(row.quantity or 0) for row in placement_rows if row.status == "placed")
    assigned = sum(float(row.quantity or 0) for row in placement_rows if row.status == "assigned")
    loaded = sum(float(row.quantity or 0) for row in placement_rows if row.status == "loaded")
    return {
        "waiting_for_placement": max(0.0, total - placed - assigned - loaded),
        "placed": placed,
        "assigned_to_shipment": assigned,
        "loaded": loaded,
    }


def create_vehicle(db: Session, data, actor: str) -> MesVehicle:
    registration = re.sub(r"\s+", "", data.registration_number.upper())
    if not registration:
        raise LogisticsError("invalid_registration", "Registration number is required", 422)
    payload = getattr(data, "max_payload_kg", None)
    if payload is None:
        payload = getattr(data, "load_capacity", None)
    for field, raw in (("max_payload_kg", payload), ("internal_length_mm", data.internal_length_mm), ("internal_width_mm", data.internal_width_mm), ("internal_height_mm", data.internal_height_mm)):
        if raw is None or float(raw) <= 0:
            raise LogisticsError("invalid_vehicle_measurement", f"{field} must be positive", 422)
    if data.max_volume_m3 is not None and float(data.max_volume_m3) <= 0:
        raise LogisticsError("invalid_vehicle_measurement", "max_volume_m3 must be positive", 422)
    vehicle = MesVehicle(
        vehicle_type=data.vehicle_type.strip(), registration_number=registration,
        internal_code=getattr(data, "internal_code", "").strip(),
        model=getattr(data, "model", "").strip(),
        driver_name=data.driver_name.strip(), driver_phone=data.driver_phone.strip(),
        max_payload_kg=payload, internal_length_mm=data.internal_length_mm,
        internal_width_mm=data.internal_width_mm, internal_height_mm=data.internal_height_mm,
        max_volume_m3=data.max_volume_m3, notes=getattr(data, "notes", "").strip(), is_active=data.is_active,
        operational_state="AVAILABLE" if data.is_active else "INACTIVE",
        created_by=actor, updated_by=actor,
    )
    db.add(vehicle)
    try:
        db.flush()
    except IntegrityError as exc:
        raise LogisticsError("vehicle_registration_exists", "Registration number already exists") from exc
    log_action(db, actor, "create", "mes_vehicle", vehicle.id, registration)
    return vehicle


def update_vehicle(db: Session, vehicle: MesVehicle, data, actor: str) -> MesVehicle:
    if vehicle.version != data.expected_version:
        raise LogisticsError("vehicle_version_conflict", "Vehicle was changed", 409)
    payload = getattr(data, "max_payload_kg", None)
    if payload is None:
        payload = getattr(data, "load_capacity", None)
    for field in ("max_payload_kg", "internal_length_mm", "internal_width_mm", "internal_height_mm"):
        value = getattr(data, field)
        if field == "max_payload_kg" and value is None:
            value = payload
        if value is not None and float(value) <= 0:
            raise LogisticsError("invalid_vehicle_measurement", f"{field} must be positive", 422)
    if data.max_volume_m3 is not None and float(data.max_volume_m3) <= 0:
        raise LogisticsError("invalid_vehicle_measurement", "max_volume_m3 must be positive", 422)
    registration = getattr(data, "registration_number", None)
    if registration is not None:
        registration = re.sub(r"\s+", "", registration.upper())
        if not registration:
            raise LogisticsError("invalid_registration", "Registration number is required", 422)
        duplicate = db.query(MesVehicle).filter(MesVehicle.registration_number == registration, MesVehicle.id != vehicle.id).first()
        if duplicate:
            raise LogisticsError("vehicle_registration_exists", "Registration number already exists", 409)
        vehicle.registration_number = registration
    for field in ("vehicle_type", "internal_code", "model", "driver_name", "driver_phone", "notes"):
        value = getattr(data, field)
        if value is not None:
            setattr(vehicle, field, value.strip())
    if data.is_active is False:
        conflict = db.query(MesTrip).filter(MesTrip.vehicle_id == vehicle.id, MesTrip.status.in_({"planned", "loading", "loaded", "dispatched", "in_transit"})).first()
        if conflict:
            raise LogisticsError("vehicle_active_trip_conflict", "Vehicle has a conflicting active trip")
        vehicle.operational_state = "INACTIVE"
    elif data.is_active is True and vehicle.operational_state == "INACTIVE":
        vehicle.operational_state = "AVAILABLE"
    for field in ("max_payload_kg", "internal_length_mm", "internal_width_mm", "internal_height_mm", "max_volume_m3", "is_active"):
        value = getattr(data, field)
        if field == "max_payload_kg" and value is None:
            value = payload
        if value is not None:
            setattr(vehicle, field, value)
    vehicle.version += 1
    vehicle.updated_by = actor
    vehicle.updated_at = datetime.utcnow()
    log_action(db, actor, "update", "mes_vehicle", vehicle.id, f"version={vehicle.version}")
    return vehicle


def create_trip(db: Session, data, actor: str) -> MesTrip:
    vehicle = db.query(MesVehicle).filter_by(id=data.vehicle_id, is_active=True, operational_state="AVAILABLE").first()
    if not vehicle:
        raise LogisticsError("vehicle_not_available", "Active vehicle not found", 404)
    driver_user_id = getattr(data, "driver_user_id", None)
    driver = db.query(User).filter_by(id=driver_user_id, role="driver", is_active=True).first() if driver_user_id else None
    if driver_user_id and not driver:
        raise LogisticsError("driver_not_available", "Active driver user not found", 404)
    project = db.query(ProductionProject).filter_by(id=data.project_id).first()
    release = db.query(ProjectReleaseSnapshot).filter_by(id=data.release_id, project_id=data.project_id).first()
    if not project or not release:
        raise LogisticsError("project_release_mismatch", "Project release does not match", 409)
    snapshots = (project.destination_city or "", project.site_name or "", project.full_address or "")
    supplied = (data.destination_city.strip(), data.destination_site.strip(), data.destination_address.strip())
    if supplied != snapshots:
        raise LogisticsError("trip_destination_mismatch", "Trip destination must match project snapshot")
    evidence_policy = getattr(data, "evidence_policy", "required")
    if evidence_policy not in {"required", "optional"}:
        raise LogisticsError("invalid_evidence_policy", "Evidence policy must be required or optional", 422)
    loading_at = getattr(data, "planned_loading_at", None)
    departure_at = getattr(data, "planned_departure_at", None)
    deadline_at = getattr(data, "delivery_deadline_at", None)
    if loading_at and departure_at and departure_at < loading_at:
        raise LogisticsError("departure_before_loading", "Planned departure cannot precede loading", 422)
    if departure_at and deadline_at and deadline_at < departure_at:
        raise LogisticsError("deadline_before_departure", "Delivery deadline cannot precede departure", 422)
    active_statuses = {"planned", "loading", "loaded", "dispatched", "in_transit"}
    if db.query(MesTrip).filter(MesTrip.vehicle_id == vehicle.id, MesTrip.status.in_(active_statuses)).first():
        raise LogisticsError("vehicle_assignment_conflict", "Vehicle has a conflicting active trip")
    if driver and db.query(MesTrip).filter(MesTrip.driver_user_id == driver.id, MesTrip.status.in_(active_statuses)).first():
        raise LogisticsError("driver_assignment_conflict", "Driver has a conflicting active trip")
    profile = db.query(UserIdentityProfile).filter_by(user_id=driver.id).first() if driver else None
    trip = MesTrip(
        trip_number=data.trip_number.strip().upper(), vehicle_id=vehicle.id,
        driver_user_id=driver.id if driver else None,
        project_id=project.id, release_id=release.id,
        driver_name_snapshot=((profile.full_name if profile else "") or driver.username) if driver else "",
        driver_phone_snapshot=(profile.phone if profile else "") if driver else "",
        destination_city=supplied[0], destination_site=supplied[1], destination_address=supplied[2],
        planned_loading_at=loading_at, planned_departure_at=departure_at,
        delivery_deadline_at=deadline_at, notes=data.notes.strip(),
        evidence_policy=evidence_policy,
        completeness_required=bool(getattr(data, "completeness_required", True)),
        created_by=actor, updated_by=actor,
    )
    db.add(trip)
    try:
        db.flush()
    except IntegrityError as exc:
        raise LogisticsError("trip_number_exists", "Trip number already exists") from exc
    log_action(db, actor, "create", "mes_trip", trip.id, trip.trip_number)
    return trip


def attach_dispatch(db: Session, trip: MesTrip, dispatch_id: int, actor: str) -> MesDispatch:
    dispatch = db.query(MesDispatch).with_for_update().filter_by(id=dispatch_id).first()
    if not dispatch:
        raise LogisticsError("dispatch_not_found", "Dispatch not found", 404)
    job = dispatch.job
    if dispatch.trip_id and dispatch.trip_id != trip.id:
        raise LogisticsError("dispatch_already_assigned", "Dispatch already belongs to another trip")
    if not job or dispatch.project_id != trip.project_id or job.project_release_snapshot_id != trip.release_id:
        raise LogisticsError("trip_project_release_mismatch", "Dispatch project or release does not match trip")
    if (dispatch.destination_city or "", dispatch.site_name or "", job.project.full_address or "") != (
        trip.destination_city, trip.destination_site, trip.destination_address,
    ):
        raise LogisticsError("trip_destination_mismatch", "Dispatch destination does not match trip")
    dispatch.trip_id = trip.id
    log_value_change(db, actor, "assign_trip", "mes_dispatch", dispatch.id, "trip_id", None, trip.id)
    return dispatch


def transition_trip(db: Session, trip: MesTrip, target: str, expected_version: int, actor: str) -> MesTrip:
    if trip.version != expected_version:
        raise LogisticsError("trip_version_conflict", "Trip was changed", 409)
    target = target.strip().lower()
    try:
        require_transition(trip.status, target)
    except TripLifecycleError as exc:
        raise LogisticsError(exc.code, str(exc), exc.status_code) from exc
    if target == "loading":
        if not trip.vehicle_id:
            raise LogisticsError("trip_vehicle_required", "Assign an available vehicle before loading", 422)
        if not trip.driver_user_id:
            raise LogisticsError("trip_driver_required", "Assign an active driver before loading", 422)
        if not trip.vehicle or not trip.vehicle.is_active or trip.vehicle.operational_state != "AVAILABLE":
            raise LogisticsError("vehicle_not_available", "Vehicle is not operationally available")
    if target in {"loaded", "dispatched", "arrived", "delivered", "accepted"}:
        raise LogisticsError("managed_transition_required", "This transition requires its transactional execution endpoint")
    old = trip.status
    trip.status = target
    trip.version += 1
    trip.updated_by = actor
    trip.updated_at = datetime.utcnow()
    if target == "dispatched":
        trip.actual_departure_at = trip.actual_departure_at or datetime.utcnow()
    if target == "delivered":
        trip.arrived_at = trip.arrived_at or datetime.utcnow()
    log_value_change(db, actor, "status", "mes_trip", trip.id, "status", old, target)
    return trip


def _detect_file(content: bytes) -> tuple[str, str]:
    lowered = content.lower()
    if b"<script" in lowered or b"<svg" in lowered or content.startswith(b"MZ"):
        raise LogisticsError("unsafe_evidence_type", "Executable or scripted content is not allowed", 415)
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", ".webp"
    if content.startswith(b"%PDF-"):
        if any(token in content for token in (b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile")):
            raise LogisticsError("unsafe_evidence_type", "Scripted or embedded PDF content is not allowed", 415)
        return "application/pdf", ".pdf"
    raise LogisticsError("unsafe_evidence_type", "Unsupported or unsafe file signature", 415)


def save_trip_evidence(db: Session, *, trip: MesTrip, evidence_type: str, content: bytes,
                       original_filename: str, claimed_mime: str, actor: str,
                       note: str = "", latitude: float | None = None,
                       longitude: float | None = None) -> MesTripEvidence:
    kind = evidence_type.strip().lower()
    if kind not in IMAGE_EVIDENCE | {POD_EVIDENCE}:
        raise LogisticsError("invalid_evidence_type", "Invalid evidence type", 422)
    if not content or len(content) > MAX_EVIDENCE_BYTES:
        raise LogisticsError("evidence_size_invalid", "Evidence file is empty or too large", 413)
    name = original_filename or "evidence"
    if PurePath(name).name != name or "\x00" in name or len(name) > 255:
        raise LogisticsError("unsafe_filename", "Unsafe evidence filename", 422)
    mime, extension = _detect_file(content)
    if kind == POD_EVIDENCE and mime != "application/pdf":
        raise LogisticsError("pod_requires_pdf", "POD evidence must be a PDF", 415)
    if kind != POD_EVIDENCE and mime == "application/pdf":
        raise LogisticsError("photo_requires_image", "Photo evidence must be JPEG, PNG, or WebP", 415)
    claimed = (claimed_mime or "").split(";", 1)[0].strip().lower()
    if claimed and claimed != mime:
        raise LogisticsError("evidence_mime_mismatch", "MIME type does not match file signature", 415)
    if latitude is not None and not -90 <= latitude <= 90:
        raise LogisticsError("invalid_gps", "Latitude is invalid", 422)
    if longitude is not None and not -180 <= longitude <= 180:
        raise LogisticsError("invalid_gps", "Longitude is invalid", 422)

    relative = Path("trip-evidence") / str(trip.project_id) / str(trip.id) / f"{uuid4().hex}{extension}"
    root = (UPLOAD_PATH / "trip-evidence").resolve()
    target = (UPLOAD_PATH / relative).resolve()
    if root != target and root not in target.parents:
        raise LogisticsError("unsafe_storage_path", "Evidence storage path is invalid", 500)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    evidence = MesTripEvidence(
        trip_id=trip.id, project_id=trip.project_id, evidence_type=kind, actor=actor,
        latitude=latitude, longitude=longitude, note=note.strip(), original_filename=name,
        mime_type=mime, file_size=len(content), checksum=hashlib.sha256(content).hexdigest(),
        storage_relative_path=relative.as_posix(),
    )
    db.add(evidence)
    db.flush()
    log_action(db, actor, "upload", "mes_trip_evidence", evidence.id, f"trip={trip.id}; type={kind}; sha256={evidence.checksum}")
    return evidence


def evidence_path(evidence: MesTripEvidence) -> Path:
    root = (UPLOAD_PATH / "trip-evidence").resolve()
    target = (UPLOAD_PATH / evidence.storage_relative_path).resolve()
    if root != target and root not in target.parents:
        raise LogisticsError("unsafe_storage_path", "Evidence storage path is invalid", 500)
    return target
