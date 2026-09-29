"""Transactional Checkpoint C shipment execution and deterministic 2D loading plan."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import (
    MesDispatch, MesFinishedGoodsInventory, MesFinishedGoodsPlacement, MesInventoryMovement,
    MesJobPackage, MesLoadingPlanPlacement, MesProductionJob, MesShipmentItem, MesTrip,
    MesTripCommand, MesTripEvidence, ProductionProject, ProductionProjectLine, AuditLog,
    ProjectProductionOperation, ProjectReleaseSnapshot,
)
from services.audit import log_action
from services.project_execution import record_absolute_operation, reconcile_project_line


class ShipmentError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 409, context: dict | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.context = context or {}


def _payload_hash(payload) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _existing_command(db: Session, trip_id: int, command_type: str, key: str, payload) -> dict | None:
    digest = _payload_hash(payload)
    row = db.query(MesTripCommand).filter_by(idempotency_key=key).first()
    if not row:
        return None
    if row.trip_id != trip_id or row.command_type != command_type or row.payload_hash != digest:
        raise ShipmentError("idempotency_key_conflict", "Idempotency key was used with a different command or payload")
    return dict(row.result_json or {})


def _finish_command(db: Session, trip: MesTrip, command_type: str, key: str, payload, result: dict, actor: str) -> dict:
    stored_result = json.loads(json.dumps(result, default=str))
    db.add(MesTripCommand(trip_id=trip.id, command_type=command_type, idempotency_key=key,
                          payload_hash=_payload_hash(payload), result_json=stored_result, actor=actor))
    try:
        db.flush()
    except IntegrityError as exc:
        raise ShipmentError("operation_already_recorded", "Concurrent command already completed") from exc
    return result


def serialize_item(item: MesShipmentItem) -> dict:
    payload = {key: getattr(item, key) for key in (
        "id", "trip_id", "dispatch_id", "placement_id", "inventory_id", "package_id",
        "project_id", "project_line_id", "template_id", "release_id", "planned_quantity",
        "assigned_quantity", "loaded_quantity", "delivered_quantity", "accepted_quantity",
        "damaged_quantity", "missing_quantity", "gross_weight_kg", "length_mm", "width_mm",
        "height_mm", "shortage_resolved", "recipient_name", "delivery_notes", "delivered_at",
        "accepted_at", "assignment_status", "version", "created_at", "updated_at",
    )}
    payload.update({
        "package_number": item.package.package_number if item.package else None,
        "product_code": item.template.code if item.template else None,
        "product_name": item.template.name if item.template else None,
        "passport_serials": [p.serial_number for p in sorted(getattr(item.package, "product_passports", []), key=lambda passport: passport.unit_index)] if item.package else [],
        "passport_count": len(getattr(item.package, "product_passports", [])) if item.package else 0,
    })
    return payload


def serialize_plan(row: MesLoadingPlanPlacement) -> dict:
    return {key: getattr(row, key) for key in (
        "id", "trip_id", "shipment_item_id", "x_mm", "y_mm", "placed_width_mm",
        "placed_length_mm", "rotation", "loading_sequence", "version", "created_at", "updated_at",
    )}


def _validate_trip_snapshot(trip: MesTrip) -> None:
    project = trip.project
    if not project or trip.release.project_id != trip.project_id:
        raise ShipmentError("trip_project_release_mismatch", "Trip project or release snapshot is invalid")
    if (trip.destination_city, trip.destination_site, trip.destination_address) != (
        project.destination_city or "", project.site_name or "", project.full_address or "",
    ):
        raise ShipmentError("trip_destination_mismatch", "Trip destination no longer matches its project snapshot")


def create_consolidated_trip(db: Session, data, actor: str) -> dict:
    """Create one canonical trip and claim packages from one or more projects."""
    placement_ids = [int(value) for value in data.placement_ids]
    if not placement_ids or len(set(placement_ids)) != len(placement_ids):
        raise ShipmentError("consolidated_selection_invalid", "Select unique finished packages", 422)
    if len(placement_ids) > 250:
        raise ShipmentError("consolidated_selection_too_large", "A trip can claim at most 250 packages at once", 422)
    payload = {
        "trip_number": data.trip_number.strip().upper(),
        "vehicle_id": data.vehicle_id,
        "driver_user_id": data.driver_user_id,
        "placement_ids": placement_ids,
        "planned_loading_at": data.planned_loading_at,
        "planned_departure_at": data.planned_departure_at,
        "delivery_deadline_at": data.delivery_deadline_at,
        "notes": data.notes.strip(),
        "evidence_policy": data.evidence_policy,
        "completeness_required": data.completeness_required,
    }
    existing_command = db.query(MesTripCommand).filter_by(idempotency_key=data.idempotency_key).first()
    if existing_command:
        if (
            existing_command.command_type != "create_consolidated_trip"
            or existing_command.payload_hash != _payload_hash(payload)
        ):
            raise ShipmentError("idempotency_key_conflict", "Idempotency key has a different payload")
        return {**dict(existing_command.result_json or {}), "idempotent": True}
    placements = db.query(MesFinishedGoodsPlacement).with_for_update().filter(
        MesFinishedGoodsPlacement.id.in_(placement_ids),
    ).all()
    by_id = {row.id: row for row in placements}
    if len(by_id) != len(placement_ids):
        raise ShipmentError("placement_not_found", "One or more selected finished packages were not found", 404)
    primary = by_id[placement_ids[0]]
    project = db.query(ProductionProject).filter_by(id=primary.project_id).first()
    if not project:
        raise ShipmentError("project_not_found", "Primary project was not found", 404)
    from services.finished_logistics import create_trip, transition_trip
    trip_data = SimpleNamespace(
        trip_number=payload["trip_number"], vehicle_id=data.vehicle_id,
        driver_user_id=data.driver_user_id, project_id=primary.project_id,
        release_id=primary.release_id, destination_city=project.destination_city or "",
        destination_site=project.site_name or "", destination_address=project.full_address or "",
        planned_loading_at=data.planned_loading_at,
        planned_departure_at=data.planned_departure_at,
        delivery_deadline_at=data.delivery_deadline_at, notes=data.notes,
        evidence_policy=data.evidence_policy,
        completeness_required=data.completeness_required,
    )
    trip = create_trip(db, trip_data, actor)
    for placement_id in placement_ids:
        child_key = f"consolidated-{hashlib.sha256(f'{data.idempotency_key}:{placement_id}'.encode()).hexdigest()[:32]}"
        assign_placement(
            db, trip.id, placement_id, dispatch_id=None, planned_quantity=None,
            idempotency_key=child_key, actor=actor,
        )
    transition_trip(db, trip, "planned", trip.version, actor)
    progress = trip_progress(db, trip)
    result = {
        "trip_id": trip.id, "trip_number": trip.trip_number, "status": trip.status,
        "trip_version": trip.version, "project_count": progress["project_count"],
        "package_count": progress["package_count"], "projects": progress["projects"],
        "stops": progress["stops"], "idempotent": False,
    }
    return _finish_command(
        db, trip, "create_consolidated_trip", data.idempotency_key, payload, result, actor,
    )


def assign_placement(db: Session, trip_id: int, placement_id: int, *, dispatch_id: int | None,
                     planned_quantity: float | None, idempotency_key: str, actor: str) -> dict:
    payload = {"placement_id": placement_id, "dispatch_id": dispatch_id, "planned_quantity": planned_quantity}
    existing = _existing_command(db, trip_id, "assign", idempotency_key, payload)
    if existing is not None:
        return {**existing, "idempotent": True}
    trip = db.query(MesTrip).with_for_update().filter_by(id=trip_id).first()
    if not trip:
        raise ShipmentError("trip_not_found", "Trip not found", 404)
    if trip.status not in {"draft", "planned", "loading"}:
        raise ShipmentError("trip_not_assignable", "Trip is not open for assignment")
    _validate_trip_snapshot(trip)
    placement = db.query(MesFinishedGoodsPlacement).with_for_update().filter_by(id=placement_id).first()
    if not placement:
        raise ShipmentError("placement_not_found", "Finished placement not found", 404)
    inventory, package = placement.inventory, placement.package
    line = db.query(ProductionProjectLine).filter_by(id=placement.project_line_id).first()
    release = db.query(ProjectReleaseSnapshot).filter_by(
        id=placement.release_id, project_id=placement.project_id,
    ).first()
    dispatch = None
    legacy_dispatch_claim = False
    if dispatch_id is not None:
        dispatch = db.query(MesDispatch).filter_by(id=dispatch_id, trip_id=trip.id).first()
        if (
            not dispatch
            or dispatch.project_id != placement.project_id
            or dispatch.job.project_release_snapshot_id != placement.release_id
        ):
            raise ShipmentError("shipment_dispatch_mismatch", "Dispatch does not match the package project and release")
        legacy_dispatch_claim = placement.status == "assigned" and any(
            row.package_id == placement.package_id for row in dispatch.packages
        )
    mismatch = (
        (placement.status != "placed" and not legacy_dispatch_claim) or not inventory or inventory.status != "in_stock" or not package
        or package.status != "placed" or not release
        or not line or line.project_id != placement.project_id
        or inventory.project_id != placement.project_id
        or inventory.project_line_id != placement.project_line_id or inventory.template_id != placement.template_id
        or inventory.project_release_snapshot_id != placement.release_id or package.project_id != placement.project_id
        or package.project_line_id != placement.project_line_id
        or package.project_release_snapshot_id != placement.release_id
        or line.product_id != placement.template_id
    )
    if mismatch:
        raise ShipmentError("shipment_item_mismatch", "Placement project, line, product, release, package, or inventory is ineligible")
    quantity = float(planned_quantity if planned_quantity is not None else placement.quantity)
    if quantity <= 0 or abs(quantity - float(placement.quantity)) > 0.0001:
        raise ShipmentError("shipment_quantity_invalid", "This phase requires assigning the complete finished placement", 422)
    facts = reconcile_project_line(db, line)
    eligible = min(facts["qc_approved_quantity"] - facts["rework_pending_quantity"], facts["packaged_quantity"], facts["finished_goods_quantity"])
    already = db.query(func.coalesce(func.sum(MesShipmentItem.assigned_quantity), 0)).filter_by(
        project_line_id=line.id, release_id=placement.release_id, assignment_status="active").scalar() or 0
    if eligible + 0.0001 < float(already) + quantity:
        raise ShipmentError("shipment_item_not_finished", "QC, rework, packaging, or finished warehouse eligibility is insufficient")
    expected_placement_status = placement.status
    claimed = db.execute(update(MesFinishedGoodsPlacement).where(
        MesFinishedGoodsPlacement.id == placement.id,
        MesFinishedGoodsPlacement.status == expected_placement_status,
        MesFinishedGoodsPlacement.version == placement.version,
    ).values(status="assigned", version=placement.version + 1, updated_by=actor, updated_at=datetime.utcnow())).rowcount
    if claimed != 1:
        raise ShipmentError("shipment_item_already_assigned", "Finished placement was claimed concurrently")
    gross = float(package.gross_weight_kg) if package.gross_weight_kg and package.gross_weight_kg > 0 else None
    template = placement.inventory.template
    dimensions = (template.length_mm, template.width_mm, template.height_mm)
    if not all(value is not None and float(value) > 0 for value in dimensions):
        dimensions = (None, None, None)
    item = MesShipmentItem(
        trip_id=trip.id, dispatch_id=dispatch.id if dispatch else None, placement_id=placement.id,
        inventory_id=inventory.id, package_id=package.id, project_id=placement.project_id,
        project_line_id=line.id, template_id=placement.template_id, release_id=placement.release_id,
        planned_quantity=quantity, assigned_quantity=quantity, gross_weight_kg=gross,
        length_mm=dimensions[0], width_mm=dimensions[1], height_mm=dimensions[2],
        created_by=actor, updated_by=actor,
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ShipmentError("shipment_item_already_assigned", "Shipment item already exists") from exc
    log_action(db, actor, "assign", "mes_shipment_item", item.id, f"trip={trip.id}; placement={placement.id}; quantity={quantity}")
    result = {"item": serialize_item(item), "idempotent": False}
    return _finish_command(db, trip, "assign", idempotency_key, payload, result, actor)


def remove_assignment(db: Session, trip_id: int, item_id: int, expected_version: int, actor: str) -> None:
    trip = db.query(MesTrip).with_for_update().filter_by(id=trip_id).first()
    item = db.query(MesShipmentItem).with_for_update().filter_by(id=item_id, trip_id=trip_id).first()
    if not trip or not item:
        raise ShipmentError("shipment_item_not_found", "Shipment item not found", 404)
    if trip.status not in {"draft", "planned"} or item.loaded_quantity > 0:
        raise ShipmentError("shipment_item_locked", "Shipment item can no longer be removed")
    if item.version != expected_version:
        raise ShipmentError("shipment_item_version_conflict", "Shipment item was changed")
    db.query(MesLoadingPlanPlacement).filter_by(shipment_item_id=item.id).delete(synchronize_session=False)
    released = db.execute(update(MesFinishedGoodsPlacement).where(
        MesFinishedGoodsPlacement.id == item.placement_id,
        MesFinishedGoodsPlacement.status == "assigned",
    ).values(status="placed", version=MesFinishedGoodsPlacement.version + 1,
             updated_by=actor, updated_at=datetime.utcnow())).rowcount
    if released != 1:
        raise ShipmentError("placement_state_conflict", "Placement state changed concurrently")
    log_action(db, actor, "remove", "mes_shipment_item", item.id, f"trip={trip.id}")
    db.delete(item)


def _rectangles_overlap(a: dict, b: dict) -> bool:
    return not (
        a["x_mm"] + a["placed_length_mm"] <= b["x_mm"]
        or b["x_mm"] + b["placed_length_mm"] <= a["x_mm"]
        or a["y_mm"] + a["placed_width_mm"] <= b["y_mm"]
        or b["y_mm"] + b["placed_width_mm"] <= a["y_mm"]
    )


def validate_plan(db: Session, trip: MesTrip, candidate: list[dict] | None = None,
                  require_complete: bool = False) -> dict:
    if not trip.vehicle or trip.vehicle.internal_length_mm <= 0 or trip.vehicle.internal_width_mm <= 0:
        raise ShipmentError("vehicle_dimensions_missing", "Vehicle cargo-floor dimensions are missing")
    items = {item.id: item for item in db.query(MesShipmentItem).filter_by(
        trip_id=trip.id, assignment_status="active",
    ).order_by(MesShipmentItem.id).all()}
    rows = candidate if candidate is not None else [serialize_plan(row) for row in db.query(
        MesLoadingPlanPlacement,
    ).filter(MesLoadingPlanPlacement.trip_id == trip.id,
             MesLoadingPlanPlacement.shipment_item_id.in_(list(items) or [-1])).all()]
    seen, sequences, normalized = set(), set(), []
    for raw in rows:
        item_id = int(raw["shipment_item_id"])
        item = items.get(item_id)
        if not item:
            raise ShipmentError("loading_plan_item_mismatch", "Loading-plan item does not belong to trip")
        if item_id in seen:
            raise ShipmentError("loading_plan_duplicate_item", "Shipment item appears more than once")
        if item.length_mm is None or item.width_mm is None or item.height_mm is None:
            raise ShipmentError("shipment_dimensions_missing", "Package dimensions are not configured", context={"item_id": item_id})
        if float(item.height_mm) > float(trip.vehicle.internal_height_mm) + 0.0001:
            raise ShipmentError("loading_plan_height_exceeded", "Package height exceeds vehicle internal height", context={"item_id": item_id})
        rotation = int(raw.get("rotation", 0))
        if rotation not in (0, 90):
            raise ShipmentError("loading_plan_rotation_invalid", "Rotation must be 0 or 90 degrees", 422)
        length = float(item.length_mm if rotation == 0 else item.width_mm)
        width = float(item.width_mm if rotation == 0 else item.length_mm)
        x, y = float(raw["x_mm"]), float(raw["y_mm"])
        sequence = int(raw["loading_sequence"])
        if x < 0 or y < 0 or length <= 0 or width <= 0 or sequence <= 0:
            raise ShipmentError("loading_plan_geometry_invalid", "Plan geometry and sequence must be positive", 422)
        if sequence in sequences:
            raise ShipmentError("loading_plan_duplicate_sequence", "Loading sequence must be unique")
        rect = {"shipment_item_id": item_id, "x_mm": x, "y_mm": y,
                "placed_length_mm": length, "placed_width_mm": width,
                "rotation": rotation, "loading_sequence": sequence,
                "expected_version": raw.get("expected_version")}
        if x + length > float(trip.vehicle.internal_length_mm) + 0.0001 or y + width > float(trip.vehicle.internal_width_mm) + 0.0001:
            raise ShipmentError("loading_plan_out_of_bounds", "Package exceeds cargo-floor boundaries", context={"item_id": item_id})
        for other in normalized:
            if _rectangles_overlap(rect, other):
                raise ShipmentError("loading_plan_overlap", "Loading-plan rectangles overlap", context={"item_id": item_id, "other_item_id": other["shipment_item_id"]})
        normalized.append(rect); seen.add(item_id); sequences.add(sequence)
    assigned_ids = {item.id for item in items.values() if item.assigned_quantity > 0}
    missing = sorted(assigned_ids - seen)
    if require_complete and missing:
        raise ShipmentError("loading_plan_incomplete", "Every assigned shipment item must be placed", context={"missing_item_ids": missing})
    known_weight = sum(float(item.gross_weight_kg) for item in items.values() if item.id in seen and item.gross_weight_kg is not None)
    unknown_count = sum(1 for item in items.values() if item.id in seen and item.gross_weight_kg is None)
    if known_weight > float(trip.vehicle.max_payload_kg) + 0.0001:
        raise ShipmentError("vehicle_payload_exceeded", "Known gross weight exceeds vehicle payload")
    occupied = sum(row["placed_length_mm"] * row["placed_width_mm"] for row in normalized)
    floor = float(trip.vehicle.internal_length_mm) * float(trip.vehicle.internal_width_mm)
    known_volume = sum(
        float(item.length_mm) * float(item.width_mm) * float(item.height_mm) / 1_000_000_000
        for item in items.values()
        if item.id in seen and item.length_mm is not None and item.width_mm is not None and item.height_mm is not None
    )
    vehicle_volume = float(trip.vehicle.max_volume_m3) if trip.vehicle.max_volume_m3 else (
        float(trip.vehicle.internal_length_mm) * float(trip.vehicle.internal_width_mm)
        * float(trip.vehicle.internal_height_mm) / 1_000_000_000
    )
    if known_volume > vehicle_volume + 0.0001:
        raise ShipmentError("vehicle_volume_exceeded", "Known package volume exceeds vehicle volume")
    return {
        "valid": True, "unit": "mm", "placements": normalized, "missing_item_ids": missing,
        "package_count": len(seen), "product_quantity": sum(float(items[item_id].planned_quantity) for item_id in seen),
        "known_gross_weight_kg": round(known_weight, 4), "unknown_weight_item_count": unknown_count,
        "weight_calculation_complete": unknown_count == 0,
        "remaining_known_payload_kg": round(float(trip.vehicle.max_payload_kg) - known_weight, 4),
        "known_volume_m3": round(known_volume, 6),
        "vehicle_volume_m3": round(vehicle_volume, 6),
        "remaining_known_volume_m3": round(vehicle_volume - known_volume, 6),
        "occupied_floor_area_mm2": round(occupied, 2), "remaining_floor_area_mm2": round(floor - occupied, 2),
        "floor_utilization_percent": round((occupied / floor * 100) if floor else 0, 2),
    }


def save_plan(db: Session, trip_id: int, placements: list[dict], actor: str) -> dict:
    trip = db.query(MesTrip).with_for_update().filter_by(id=trip_id).first()
    if not trip:
        raise ShipmentError("trip_not_found", "Trip not found", 404)
    if trip.status not in {"draft", "planned", "loading"}:
        raise ShipmentError("loading_plan_locked", "Loading plan can no longer be edited")
    existing = {row.shipment_item_id: row for row in db.query(MesLoadingPlanPlacement).filter_by(trip_id=trip.id).all()}
    target_ids = {int(raw["shipment_item_id"]) for raw in placements}
    combined = list(placements) + [
        {**serialize_plan(row), "expected_version": row.version}
        for item_id, row in existing.items() if item_id not in target_ids
    ]
    validation = validate_plan(db, trip, combined, require_complete=False)
    normalized_targets = [raw for raw in validation["placements"] if raw["shipment_item_id"] in target_ids]
    # Move existing target sequences to a collision-free positive range first so
    # a full-plan sequence swap remains atomic under the unique constraint.
    temp_base = max([row.loading_sequence for row in existing.values()] + [0]) + len(existing) + len(placements) + 1000
    for offset, raw in enumerate(normalized_targets, 1):
        row = existing.get(raw["shipment_item_id"])
        if row:
            expected = raw.get("expected_version")
            if expected is None or int(expected) != row.version:
                raise ShipmentError("loading_plan_version_conflict", "Loading-plan item was changed")
            staged = db.execute(update(MesLoadingPlanPlacement).where(
                MesLoadingPlanPlacement.id == row.id,
                MesLoadingPlanPlacement.version == int(expected),
            ).values(loading_sequence=temp_base + offset)).rowcount
            if staged != 1:
                raise ShipmentError("loading_plan_version_conflict", "Loading-plan item was changed concurrently")
    for raw in normalized_targets:
        row = existing.get(raw["shipment_item_id"])
        if row:
            expected = raw.get("expected_version")
            if expected is None or int(expected) != row.version:
                raise ShipmentError("loading_plan_version_conflict", "Loading-plan item was changed")
            changed = db.execute(update(MesLoadingPlanPlacement).where(
                MesLoadingPlanPlacement.id == row.id,
                MesLoadingPlanPlacement.version == int(expected),
            ).values(x_mm=raw["x_mm"], y_mm=raw["y_mm"],
                     placed_width_mm=raw["placed_width_mm"], placed_length_mm=raw["placed_length_mm"],
                     rotation=raw["rotation"], loading_sequence=raw["loading_sequence"],
                     version=int(expected) + 1, updated_by=actor, updated_at=datetime.utcnow())).rowcount
            if changed != 1:
                raise ShipmentError("loading_plan_version_conflict", "Loading-plan item was changed concurrently")
        else:
            db.add(MesLoadingPlanPlacement(
                trip_id=trip.id, shipment_item_id=raw["shipment_item_id"], x_mm=raw["x_mm"], y_mm=raw["y_mm"],
                placed_width_mm=raw["placed_width_mm"], placed_length_mm=raw["placed_length_mm"],
                rotation=raw["rotation"], loading_sequence=raw["loading_sequence"], created_by=actor, updated_by=actor,
            ))
    try:
        db.flush()
    except IntegrityError as exc:
        raise ShipmentError("loading_plan_claim_conflict", "Loading-plan item or sequence was claimed concurrently") from exc
    log_action(db, actor, "update", "mes_loading_plan", trip.id, f"placements={len(placements)}")
    return validate_plan(db, trip, require_complete=False)


def automatic_initial_plan(db: Session, trip: MesTrip) -> dict:
    """Deterministic first-fit candidate-edge packing; intentionally not an optimizer."""
    items = db.query(MesShipmentItem).filter_by(trip_id=trip.id, assignment_status="active").all()
    missing = [item.id for item in items if not item.length_mm or not item.width_mm or not item.height_mm
               or float(item.height_mm) > float(trip.vehicle.internal_height_mm)]
    sortable = [item for item in items if item.id not in missing]
    sortable.sort(key=lambda item: (-(float(item.length_mm) * float(item.width_mm)), item.id))
    placed, unplaced = [], list(missing)
    for sequence, item in enumerate(sortable, 1):
        candidates = {(0.0, 0.0)}
        for row in placed:
            candidates.add((row["x_mm"] + row["placed_length_mm"], row["y_mm"]))
            candidates.add((row["x_mm"], row["y_mm"] + row["placed_width_mm"]))
        chosen = None
        for x, y in sorted(candidates, key=lambda value: (value[1], value[0])):
            for rotation in (0, 90):
                length = float(item.length_mm if rotation == 0 else item.width_mm)
                width = float(item.width_mm if rotation == 0 else item.length_mm)
                rect = {"shipment_item_id": item.id, "x_mm": x, "y_mm": y,
                        "placed_length_mm": length, "placed_width_mm": width,
                        "rotation": rotation, "loading_sequence": sequence}
                if x + length > trip.vehicle.internal_length_mm or y + width > trip.vehicle.internal_width_mm:
                    continue
                if any(_rectangles_overlap(rect, other) for other in placed):
                    continue
                chosen = rect; break
            if chosen: break
        if chosen: placed.append(chosen)
        else: unplaced.append(item.id)
    return {"strategy": "deterministic_first_fit_candidate_edges_largest_area_first",
            "optimal": False, "unit": "mm", "placements": placed, "unplaced_item_ids": sorted(unplaced)}


def _has_evidence(db: Session, trip_id: int, kinds: set[str]) -> bool:
    return db.query(MesTripEvidence).filter(MesTripEvidence.trip_id == trip_id, MesTripEvidence.evidence_type.in_(kinds)).first() is not None


def _require_evidence(db: Session, trip: MesTrip, transition: str) -> None:
    if trip.evidence_policy == "optional":
        return
    required = {
        "loading": {"loaded_truck", "loaded_truck_photo"},
        "dispatch": {"departure", "departure_photo"},
        "delivery": {"arrival", "arrival_photo", "unloading", "unloading_photo"},
        "acceptance": {"acceptance_photo", "pod_document"},
    }[transition]
    if not _has_evidence(db, trip.id, required):
        raise ShipmentError("required_evidence_missing", f"Required {transition} evidence is missing", context={"accepted_types": sorted(required)})


def _movement(db: Session, item: MesShipmentItem, kind: str, actor: str) -> None:
    db.add(MesInventoryMovement(inventory_id=item.inventory_id, job_id=item.inventory.job_id,
                                package_id=item.package_id, movement_type=kind,
                                from_location_id=item.placement.location_id, quantity=item.planned_quantity,
                                performed_by=actor, notes=f"Trip {item.trip.trip_number} {kind}"))


def _record_item_operations(db: Session, trip: MesTrip, operation_type: str, quantity_field: str, actor: str) -> None:
    jobs = {}
    for item in trip.shipment_items:
        job = item.inventory.job
        jobs[job.id] = job
    for job_id, job in jobs.items():
        query = db.query(func.coalesce(func.sum(getattr(MesShipmentItem, quantity_field)), 0)).join(
            MesFinishedGoodsInventory, MesFinishedGoodsInventory.id == MesShipmentItem.inventory_id
        ).join(MesTrip, MesTrip.id == MesShipmentItem.trip_id).filter(
            MesFinishedGoodsInventory.job_id == job_id,
            MesShipmentItem.assignment_status == "active",
        )
        if operation_type == "trip_dispatched":
            query = query.filter(MesTrip.status.in_(("dispatched", "in_transit", "delivered", "accepted")))
        elif operation_type == "trip_accepted":
            query = query.filter(MesShipmentItem.accepted_at.is_not(None))
        quantity = float(query.scalar() or 0)
        if quantity > 0:
            record_absolute_operation(db, job, operation_type=operation_type,
                                      absolute_quantity=quantity, username=actor, terminal="trip",
                                      source_record_type="mes_shipment_item")


def _require_trip_completeness(db: Session, trip: MesTrip, items: list[MesShipmentItem]) -> None:
    if not trip.completeness_required:
        return
    current = defaultdict(float)
    for item in items:
        current[item.project_line_id] += float(item.planned_quantity)
    project_ids = sorted({item.project_id for item in items})
    lines = db.query(ProductionProjectLine).filter(
        ProductionProjectLine.project_id.in_(project_ids or [-1]),
    ).all()
    for line in lines:
        prior_items = db.query(MesShipmentItem).join(MesTrip, MesTrip.id == MesShipmentItem.trip_id).filter(
            MesShipmentItem.project_line_id == line.id,
            MesTrip.id != trip.id,
            MesTrip.status == "accepted",
        ).all()
        prior = sum(float(item.accepted_quantity) + (
            float(item.damaged_quantity + item.missing_quantity) if item.shortage_resolved else 0.0
        ) for item in prior_items)
        remaining = max(0.0, float(line.quantity) - prior)
        if current[line.id] + 0.0001 < remaining:
            raise ShipmentError("shipment_completeness_required", "Complete shipment policy requires every remaining project-line quantity",
                                context={"project_line_id": line.id, "required_quantity": remaining,
                                         "planned_quantity": current[line.id]})


def confirm_loading(db: Session, trip_id: int, *, acknowledge_unknown_weight: bool,
                    idempotency_key: str, actor: str) -> dict:
    payload = {"acknowledge_unknown_weight": acknowledge_unknown_weight}
    existing = _existing_command(db, trip_id, "confirm_loading", idempotency_key, payload)
    if existing is not None: return {**existing, "idempotent": True}
    trip = db.query(MesTrip).with_for_update().filter_by(id=trip_id).first()
    if not trip: raise ShipmentError("trip_not_found", "Trip not found", 404)
    if trip.status != "loading": raise ShipmentError("trip_not_loading", "Trip must be in loading state")
    _validate_trip_snapshot(trip); _require_evidence(db, trip, "loading")
    validation = validate_plan(db, trip, require_complete=True)
    if validation["unknown_weight_item_count"] and not acknowledge_unknown_weight:
        raise ShipmentError("unknown_weight_acknowledgement_required", "Unknown gross weight requires explicit acknowledgement")
    items = db.query(MesShipmentItem).with_for_update().filter_by(
        trip_id=trip.id, assignment_status="active",
    ).order_by(MesShipmentItem.id).all()
    if not items:
        raise ShipmentError("shipment_empty", "Trip has no assigned shipment items")
    _require_trip_completeness(db, trip, items)
    if trip.completeness_required and any(abs(item.assigned_quantity - item.planned_quantity) > 0.0001 for item in items):
        raise ShipmentError("shipment_completeness_required", "All planned quantities must be assigned")
    trip_claim = db.execute(update(MesTrip).where(MesTrip.id == trip.id, MesTrip.status == "loading").values(
        status="loaded", version=trip.version + 1, updated_by=actor, updated_at=datetime.utcnow())).rowcount
    if trip_claim != 1:
        raise ShipmentError("loading_state_conflict", "Trip loading was confirmed concurrently")
    db.expire(trip); db.refresh(trip)
    for item in items:
        if abs(float(item.loaded_quantity) - float(item.assigned_quantity)) <= 0.0001:
            continue
        changed = db.execute(update(MesShipmentItem).where(
            MesShipmentItem.id == item.id,
            MesShipmentItem.assignment_status == "active",
            MesShipmentItem.loaded_quantity == 0,
        ).values(loaded_quantity=item.assigned_quantity, version=item.version + 1,
                 updated_by=actor, updated_at=datetime.utcnow())).rowcount
        if changed != 1: raise ShipmentError("loading_state_conflict", "Shipment item was loaded concurrently")
        placement_changed = db.execute(update(MesFinishedGoodsPlacement).where(
            MesFinishedGoodsPlacement.id == item.placement_id, MesFinishedGoodsPlacement.status == "assigned"
        ).values(status="loaded", version=MesFinishedGoodsPlacement.version + 1,
                 updated_by=actor, updated_at=datetime.utcnow())).rowcount
        if placement_changed != 1: raise ShipmentError("loading_state_conflict", "Finished placement changed concurrently")
        inventory_changed = db.execute(update(MesFinishedGoodsInventory).where(MesFinishedGoodsInventory.id == item.inventory_id,
                   MesFinishedGoodsInventory.status == "in_stock").values(status="loaded", updated_at=datetime.utcnow())).rowcount
        if inventory_changed != 1: raise ShipmentError("loading_state_conflict", "Finished inventory changed concurrently")
        db.refresh(item); _movement(db, item, "trip_load", actor)
    _record_item_operations(db, trip, "trip_loaded", "loaded_quantity", actor)
    log_action(db, actor, "confirm_loading", "mes_trip", trip.id, f"items={len(items)}")
    result = {"trip_id": trip.id, "status": trip.status, "trip_version": trip.version,
              "validation": validation, "idempotent": False}
    return _finish_command(db, trip, "confirm_loading", idempotency_key, payload, result, actor)


def final_dispatch(db: Session, trip_id: int, *, idempotency_key: str, actor: str) -> dict:
    payload = {"dispatch": True}
    existing = _existing_command(db, trip_id, "dispatch", idempotency_key, payload)
    if existing is not None: return {**existing, "idempotent": True}
    trip = db.query(MesTrip).with_for_update().filter_by(id=trip_id).first()
    if not trip: raise ShipmentError("trip_not_found", "Trip not found", 404)
    if trip.status != "loaded": raise ShipmentError("trip_not_loaded", "Trip must be loaded before dispatch")
    if not trip.vehicle_id: raise ShipmentError("trip_vehicle_required", "Assign a vehicle before dispatch", 422)
    if not trip.driver_user_id: raise ShipmentError("trip_driver_required", "Assign a driver before dispatch", 422)
    if not trip.vehicle or not trip.vehicle.is_active or trip.vehicle.operational_state != "AVAILABLE":
        raise ShipmentError("vehicle_not_available", "Vehicle is not operationally available")
    conflicting_states = ("planned", "loading", "loaded", "dispatched", "in_transit", "arrived")
    vehicle_conflict = db.query(MesTrip.id).filter(
        MesTrip.id != trip.id, MesTrip.vehicle_id == trip.vehicle_id,
        MesTrip.status.in_(conflicting_states),
    ).first()
    if vehicle_conflict:
        raise ShipmentError("vehicle_assignment_conflict", "Vehicle already has another active trip", 409)
    driver_conflict = db.query(MesTrip.id).filter(
        MesTrip.id != trip.id, MesTrip.driver_user_id == trip.driver_user_id,
        MesTrip.status.in_(conflicting_states),
    ).first()
    if driver_conflict:
        raise ShipmentError("driver_assignment_conflict", "Driver already has another active trip", 409)
    _validate_trip_snapshot(trip); _require_evidence(db, trip, "dispatch")
    items = db.query(MesShipmentItem).with_for_update().filter_by(
        trip_id=trip.id, assignment_status="active",
    ).all()
    if not items: raise ShipmentError("shipment_empty", "Trip has no shipment items")
    _require_trip_completeness(db, trip, items)
    if trip.completeness_required and any(abs(item.loaded_quantity - item.planned_quantity) > 0.0001 for item in items):
        raise ShipmentError("shipment_completeness_required", "Complete shipment policy requires every item loaded")
    now = datetime.utcnow()
    trip_claim = db.execute(update(MesTrip).where(MesTrip.id == trip.id, MesTrip.status == "loaded").values(
        status="dispatched", actual_departure_at=now, version=trip.version + 1,
        updated_by=actor, updated_at=now)).rowcount
    if trip_claim != 1: raise ShipmentError("dispatch_state_conflict", "Trip was dispatched concurrently")
    db.expire(trip); db.refresh(trip)
    affected_project_ids = set()
    for item in items:
        release = db.query(ProjectReleaseSnapshot).filter_by(
            id=item.release_id, project_id=item.project_id,
        ).first()
        if not release:
            raise ShipmentError("shipment_item_mismatch", "Shipment item project or release changed")
        affected_project_ids.add(item.project_id)
        changed = db.execute(update(MesFinishedGoodsInventory).where(MesFinishedGoodsInventory.id == item.inventory_id,
                   MesFinishedGoodsInventory.status == "loaded").values(status="dispatched", updated_at=now)).rowcount
        if changed != 1: raise ShipmentError("dispatch_state_conflict", "Finished inventory changed before dispatch")
        _movement(db, item, "trip_dispatch", actor)
    for dispatch in trip.dispatches:
        matching_item = next((item for item in items if item.dispatch_id == dispatch.id), None)
        if not matching_item or dispatch.project_id != matching_item.project_id or dispatch.job.project_release_snapshot_id != matching_item.release_id:
            raise ShipmentError("shipment_dispatch_mismatch", "Dispatch project or release changed")
        dispatch.status = "shipped"; dispatch.ship_date = now; dispatch.updated_at = now
    _record_item_operations(db, trip, "trip_dispatched", "loaded_quantity", actor)
    for project in db.query(ProductionProject).filter(ProductionProject.id.in_(affected_project_ids)).all():
        if project.status not in {"completed", "cancelled"}:
            project.status = "shipped"
            project.updated_at = now
    log_action(db, actor, "dispatch", "mes_trip", trip.id, f"items={len(items)}")
    from models import MesTripTrackingSession
    tracking = db.query(MesTripTrackingSession).filter_by(trip_id=trip.id, status="active").order_by(
        MesTripTrackingSession.id.desc()).first()
    result = {"trip_id": trip.id, "status": trip.status, "trip_version": trip.version,
              "actual_departure_at": now.isoformat(), "tracking_session_id": tracking.id if tracking else None,
              "tracking_start_required": tracking is None, "idempotent": False}
    return _finish_command(db, trip, "dispatch", idempotency_key, payload, result, actor)


def record_delivery(db: Session, trip_id: int, dispositions: list[dict], *, idempotency_key: str, actor: str) -> dict:
    payload = {"dispositions": dispositions}
    existing = _existing_command(db, trip_id, "delivery", idempotency_key, payload)
    if existing is not None: return {**existing, "idempotent": True}
    trip = db.query(MesTrip).with_for_update().filter_by(id=trip_id).first()
    if not trip: raise ShipmentError("trip_not_found", "Trip not found", 404)
    if trip.status not in {"in_transit", "arrived"}: raise ShipmentError("trip_not_arrived", "Trip must be in transit or arrived before delivery")
    _validate_trip_snapshot(trip); _require_evidence(db, trip, "delivery")
    items = {item.id: item for item in db.query(MesShipmentItem).with_for_update().filter_by(
        trip_id=trip.id, assignment_status="active",
    ).all()}
    if not dispositions: raise ShipmentError("delivery_empty", "Delivery requires at least one item disposition", 422)
    seen = set(); now = datetime.utcnow(); expected_version = trip.version
    trip_claim = db.execute(update(MesTrip).where(
        MesTrip.id == trip.id, MesTrip.status.in_(("in_transit", "arrived")), MesTrip.version == expected_version
    ).values(version=expected_version + 1, updated_by=actor, updated_at=now)).rowcount
    if trip_claim != 1: raise ShipmentError("delivery_state_conflict", "Delivery was recorded concurrently")
    db.expire(trip); db.refresh(trip)
    for row in dispositions:
        item_id = int(row["item_id"])
        if item_id in seen or item_id not in items: raise ShipmentError("delivery_item_mismatch", "Delivery item is duplicated or not on trip")
        delivered, accepted = float(row["delivered_quantity"]), float(row["accepted_quantity"])
        damaged, missing = float(row["damaged_quantity"]), float(row["missing_quantity"])
        if min(delivered, accepted, damaged, missing) < 0 or delivered > items[item_id].loaded_quantity + 0.0001:
            raise ShipmentError("delivery_quantity_invalid", "Delivery quantities are negative or exceed loaded quantity", 422)
        if abs(delivered - accepted - damaged - missing) > 0.0001:
            raise ShipmentError("delivery_balance_invalid", "Delivered must equal accepted plus damaged plus missing", 422)
        item = items[item_id]; item.delivered_quantity = delivered; item.accepted_quantity = accepted
        item.damaged_quantity = damaged; item.missing_quantity = missing; item.delivered_at = now
        item.delivery_notes = str(row.get("notes") or "").strip(); item.version += 1; item.updated_by = actor; item.updated_at = now
        db.execute(update(MesFinishedGoodsInventory).where(MesFinishedGoodsInventory.id == item.inventory_id).values(
            status="delivered" if delivered > 0 else "dispatched", updated_at=now))
        _movement(db, item, "trip_delivery", actor); seen.add(item_id)
    db.flush()
    complete = all(float(item.delivered_quantity or 0) >= float(item.loaded_quantity or 0) - 0.0001 for item in items.values())
    if complete:
        trip.status = "delivered"; trip.arrived_at = trip.arrived_at or now
        for dispatch in trip.dispatches:
            dispatch.status = "delivered"; dispatch.delivered_at = now; dispatch.updated_at = now
    _record_item_operations(db, trip, "trip_delivered", "delivered_quantity", actor)
    project_statuses = {
        project_id: _synchronize_delivery_project(db, project_id)
        for project_id in sorted({item.project_id for item in items.values()})
    }
    log_action(db, actor, "delivery", "mes_trip", trip.id, f"items={len(seen)}")
    result = {"trip_id": trip.id, "status": trip.status, "trip_version": trip.version,
              "complete": complete, "project_statuses": project_statuses,
              "delivered_item_ids": sorted(seen), "idempotent": False}
    return _finish_command(db, trip, "delivery", idempotency_key, payload, result, actor)


def accept_delivery(db: Session, trip_id: int, *, recipient_name: str, notes: str,
                    resolved_shortage_item_ids: list[int], idempotency_key: str, actor: str,
                    project_id: int | None = None) -> dict:
    command_type = f"acceptance:{project_id}" if project_id is not None else "acceptance"
    payload = {
        "recipient_name": recipient_name,
        "notes": notes,
        "resolved_shortage_item_ids": sorted(resolved_shortage_item_ids),
        "project_id": project_id,
    }
    existing = _existing_command(db, trip_id, command_type, idempotency_key, payload)
    if existing is not None: return {**existing, "idempotent": True}
    trip = db.query(MesTrip).with_for_update().filter_by(id=trip_id).first()
    if not trip: raise ShipmentError("trip_not_found", "Trip not found", 404)
    if trip.status not in {"in_transit", "arrived", "delivered"}:
        raise ShipmentError("trip_not_delivered", "Trip must have delivered cargo before acceptance")
    if not recipient_name.strip(): raise ShipmentError("recipient_required", "Recipient name is required", 422)
    _require_evidence(db, trip, "acceptance")
    item_query = db.query(MesShipmentItem).with_for_update().filter_by(
        trip_id=trip.id, assignment_status="active",
    )
    if project_id is not None:
        item_query = item_query.filter(MesShipmentItem.project_id == project_id)
    items = item_query.all()
    if not items:
        raise ShipmentError("acceptance_project_empty", "Trip has no active cargo for this project", 404)
    if any(float(item.delivered_quantity or 0) < float(item.loaded_quantity or 0) - 0.0001 for item in items):
        raise ShipmentError("project_not_delivered", "All selected project cargo must be delivered before acceptance")
    resolved = set(resolved_shortage_item_ids)
    if resolved - {item.id for item in items}: raise ShipmentError("shortage_item_mismatch", "Resolved shortage item is not on trip")
    now = datetime.utcnow()
    expected_version = trip.version
    trip_claim = db.execute(update(MesTrip).where(
        MesTrip.id == trip.id,
        MesTrip.status.in_(("in_transit", "arrived", "delivered")),
        MesTrip.version == expected_version,
    ).values(version=expected_version + 1, updated_by=actor, updated_at=now)).rowcount
    if trip_claim != 1: raise ShipmentError("acceptance_state_conflict", "Acceptance was recorded concurrently")
    db.expire(trip); db.refresh(trip)
    for item in items:
        item.recipient_name = recipient_name.strip(); item.accepted_at = now
        item.shortage_resolved = item.id in resolved; item.delivery_notes = notes.strip() or item.delivery_notes
        item.version += 1; item.updated_by = actor; item.updated_at = now
    db.flush()
    _record_item_operations(db, trip, "trip_accepted", "accepted_quantity", actor)
    project_statuses = {
        project_id: _synchronize_delivery_project(db, project_id)
        for project_id in sorted({item.project_id for item in items})
    }
    remaining = db.query(MesShipmentItem).filter_by(
        trip_id=trip.id, assignment_status="active", accepted_at=None,
    ).count()
    if remaining == 0:
        trip.status = "accepted"
        for dispatch in trip.dispatches:
            dispatch.status = "accepted"; dispatch.accepted_at = now; dispatch.updated_at = now
    log_action(db, actor, "acceptance", "mes_trip", trip.id,
               f"recipient={recipient_name.strip()}; project={project_id or 'all'}; projects={project_statuses}")
    result = {"trip_id": trip.id, "status": trip.status, "trip_version": trip.version,
              "project_status": project_statuses.get(trip.project_id),
              "project_statuses": project_statuses,
              "project_id": project_id, "trip_complete": remaining == 0,
              "accepted_at": now.isoformat(), "idempotent": False}
    return _finish_command(db, trip, command_type, idempotency_key, payload, result, actor)


def _synchronize_delivery_project(db: Session, project_id: int) -> str:
    project = db.query(ProductionProject).with_for_update().filter_by(id=project_id).first()
    lines = db.query(ProductionProjectLine).filter_by(project_id=project_id).all()
    for line in lines:
        items = db.query(MesShipmentItem).filter_by(project_line_id=line.id).all()
        accepted_items = [item for item in items if item.accepted_at is not None]
        line.delivered_quantity = min(float(line.quantity), sum(float(item.delivered_quantity) for item in items))
        line.accepted_quantity = min(float(line.quantity), sum(float(item.accepted_quantity) for item in accepted_items))
        line.damaged_quantity = sum(float(item.damaged_quantity) for item in items)
        line.missing_quantity = sum(float(item.missing_quantity) for item in items)
    complete = bool(lines) and all(
        line.accepted_quantity + sum(
            float(item.damaged_quantity + item.missing_quantity)
            for item in db.query(MesShipmentItem).filter_by(project_line_id=line.id, shortage_resolved=True).all()
            if item.accepted_at is not None
        ) >= float(line.quantity) - 0.0001 for line in lines
    )
    any_delivered = any(line.delivered_quantity > 0 for line in lines)
    all_delivered = bool(lines) and all(line.delivered_quantity >= float(line.quantity) - 0.0001 for line in lines)
    project.status = "completed" if complete else ("delivered" if all_delivered else ("partially_delivered" if any_delivered else project.status))
    if complete: project.completed_at = datetime.utcnow()
    project.updated_at = datetime.utcnow()
    return project.status


def trip_progress(db: Session, trip: MesTrip) -> dict:
    all_items = db.query(MesShipmentItem).filter_by(trip_id=trip.id).all()
    items = [item for item in all_items if item.assignment_status == "active"]
    fields = ("planned_quantity", "assigned_quantity", "loaded_quantity", "delivered_quantity", "accepted_quantity", "damaged_quantity", "missing_quantity")
    totals = {field: round(sum(float(getattr(item, field) or 0) for item in items), 4) for field in fields}
    history = [
        {"kind": "command", "type": row.command_type, "actor": row.actor, "at": row.created_at, "id": row.id}
        for row in db.query(MesTripCommand).filter_by(trip_id=trip.id).all()
    ] + [
        {"kind": "evidence", "type": row.evidence_type, "actor": row.actor, "at": row.occurred_at, "id": row.id}
        for row in db.query(MesTripEvidence).filter_by(trip_id=trip.id).all()
    ] + [
        {"kind": "inventory_movement", "type": row.movement_type, "actor": row.performed_by, "at": row.created_at, "id": row.id}
        for row in db.query(MesInventoryMovement).filter(
            MesInventoryMovement.inventory_id.in_([item.inventory_id for item in items])
        ).all()
    ] + [
        {"kind": "audit", "type": row.action, "actor": row.username, "at": row.created_at, "id": row.id}
        for row in db.query(AuditLog).filter_by(entity_type="mes_trip", entity_id=trip.id).all()
    ]
    history.sort(key=lambda row: (row["at"], row["id"]))
    projects = {}
    for item in items:
        project = item.project_line.project if item.project_line else None
        bucket = projects.setdefault(item.project_id, {
            "project_id": item.project_id,
            "project_code": project.project_code if project else f"#{item.project_id}",
            "project_name": project.project_name if project else "",
            "destination_city": project.destination_city if project else "",
            "destination_site": project.site_name if project else "",
            "package_count": 0, "assigned_quantity": 0.0, "loaded_quantity": 0.0,
            "delivered_quantity": 0.0, "accepted_quantity": 0.0,
        })
        bucket["package_count"] += 1
        for key in ("assigned_quantity", "loaded_quantity", "delivered_quantity", "accepted_quantity"):
            bucket[key] = round(bucket[key] + float(getattr(item, key) or 0), 4)
    from services.load_corrections import capacity_summary, correction_history
    corrections = correction_history(db, trip.id)
    history.extend({
        "kind": "load_correction", "type": row["action"].lower(), "actor": row["actor"],
        "at": row["created_at"], "id": row["id"],
    } for row in corrections)
    history.sort(key=lambda row: (row["at"], row["id"]))
    return {"trip_id": trip.id, "status": trip.status, "totals": totals,
            "project_count": len(projects), "package_count": len(items),
            "projects": list(projects.values()), "stops": [
                {"project_id": row["project_id"], "city": row["destination_city"], "site": row["destination_site"]}
                for row in projects.values()
            ],
            "items": [serialize_item(item) for item in items],
            "inactive_items": [serialize_item(item) for item in all_items if item.assignment_status != "active"],
            "capacity": capacity_summary(db, trip) if trip.vehicle else None,
            "corrections": corrections, "history": history}
