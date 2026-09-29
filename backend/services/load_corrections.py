"""Transactional, append-only corrections for canonical trip loading.

Shipment items remain the authoritative package-to-trip claims.  A correction
never deletes a loaded shipment row: its current quantities are cleared and an
append-only MesLoadCorrection explains the physical movement.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import (
    MesFinishedGoodsInventory,
    MesFinishedGoodsPlacement,
    MesInventoryMovement,
    MesLoadCorrection,
    MesLoadingPlanPlacement,
    MesShipmentItem,
    MesTrip,
)
from services.audit import log_action
from services.shipment_execution import ShipmentError, automatic_initial_plan, serialize_item


CORRECTION_REASONS = {
    "wrong_truck",
    "wrong_package",
    "wrong_destination",
    "damaged_before_dispatch",
    "capacity_correction",
    "customer_change",
    "other",
}
PRE_DISPATCH_STATUSES = {"loading", "loaded"}


def _payload_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def serialize_correction(row: MesLoadCorrection) -> dict:
    return {
        "id": row.id,
        "trip_id": row.trip_id,
        "target_trip_id": row.target_trip_id,
        "shipment_item_id": row.shipment_item_id,
        "target_shipment_item_id": row.target_shipment_item_id,
        "package_id": row.package_id,
        "replacement_package_id": row.replacement_package_id,
        "package_number": row.package.package_number if row.package else None,
        "replacement_package_number": (
            row.replacement_package.package_number if row.replacement_package else None
        ),
        "from_trip_number": row.trip.trip_number if row.trip else None,
        "to_trip_number": row.target_trip.trip_number if row.target_trip else None,
        "action": row.action,
        "reason": row.reason,
        "notes": row.notes,
        "actor": row.actor,
        "created_at": row.created_at,
    }


def correction_history(db: Session, trip_id: int) -> list[dict]:
    rows = (
        db.query(MesLoadCorrection)
        .filter(or_(MesLoadCorrection.trip_id == trip_id, MesLoadCorrection.target_trip_id == trip_id))
        .order_by(MesLoadCorrection.created_at, MesLoadCorrection.id)
        .all()
    )
    return [serialize_correction(row) for row in rows]


def _existing(db: Session, *, trip_id: int, action: str, key: str, payload: dict) -> dict | None:
    row = db.query(MesLoadCorrection).filter_by(idempotency_key=key).first()
    if not row:
        return None
    if row.trip_id != trip_id or row.action != action or row.payload_hash != _payload_hash(payload):
        raise ShipmentError(
            "idempotency_key_conflict",
            "Idempotency key was used with a different loading correction",
        )
    return {**dict(row.result_json or {}), "idempotent": True}


def _store(
    db: Session,
    *,
    trip: MesTrip,
    item: MesShipmentItem,
    action: str,
    reason: str,
    notes: str,
    key: str,
    payload: dict,
    actor: str,
    result: dict,
    target_trip: MesTrip | None = None,
    target_item: MesShipmentItem | None = None,
    replacement_package_id: int | None = None,
) -> dict:
    stored = json.loads(json.dumps(result, default=str))
    row = MesLoadCorrection(
        trip_id=trip.id,
        target_trip_id=target_trip.id if target_trip else None,
        shipment_item_id=item.id,
        target_shipment_item_id=target_item.id if target_item else None,
        package_id=item.package_id,
        replacement_package_id=replacement_package_id,
        action=action,
        reason=reason,
        notes=notes.strip(),
        payload_hash=_payload_hash(payload),
        result_json=stored,
        idempotency_key=key,
        actor=actor,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ShipmentError("operation_already_recorded", "Loading correction completed concurrently") from exc
    log_action(
        db,
        actor,
        action.lower(),
        "mes_load_correction",
        row.id,
        f"trip={trip.id}; target_trip={target_trip.id if target_trip else ''}; package={item.package_id}",
    )
    return result


def _validate_reason(reason: str) -> str:
    normalized = str(reason or "").strip().lower()
    if normalized not in CORRECTION_REASONS:
        raise ShipmentError(
            "load_correction_reason_invalid",
            "Select a supported loading-correction reason",
            422,
        )
    return normalized


def _locked_trip_item(
    db: Session,
    trip_id: int,
    item_id: int,
    *,
    expected_trip_version: int,
    expected_item_version: int,
) -> tuple[MesTrip, MesShipmentItem]:
    trip = db.query(MesTrip).with_for_update().filter_by(id=trip_id).first()
    item = db.query(MesShipmentItem).with_for_update().filter_by(id=item_id, trip_id=trip_id).first()
    if not trip or not item:
        raise ShipmentError("shipment_item_not_found", "Shipment item not found", 404)
    if trip.version != expected_trip_version:
        raise ShipmentError("trip_version_conflict", "Trip was changed", 409)
    if item.version != expected_item_version:
        raise ShipmentError("shipment_item_version_conflict", "Shipment item was changed", 409)
    if trip.status not in PRE_DISPATCH_STATUSES:
        if trip.status in {"dispatched", "in_transit", "arrived", "delivered", "accepted"}:
            raise ShipmentError(
                "post_dispatch_exception_required",
                "Dispatched cargo requires the controlled logistics-exception workflow",
                409,
            )
        raise ShipmentError("load_correction_not_allowed", "Trip is not in a correctable loading state", 409)
    return trip, item


def capacity_summary(db: Session, trip: MesTrip) -> dict:
    if not trip.vehicle:
        raise ShipmentError("trip_vehicle_required", "Trip requires a vehicle", 422)
    items = db.query(MesShipmentItem).filter_by(trip_id=trip.id, assignment_status="active").all()
    known_weight = sum(float(item.gross_weight_kg) for item in items if item.gross_weight_kg is not None)
    unknown_weight = sum(1 for item in items if item.gross_weight_kg is None)
    known_volume = sum(
        float(item.length_mm) * float(item.width_mm) * float(item.height_mm) / 1_000_000_000
        for item in items
        if item.length_mm is not None and item.width_mm is not None and item.height_mm is not None
    )
    unknown_volume = sum(
        1 for item in items
        if item.length_mm is None or item.width_mm is None or item.height_mm is None
    )
    vehicle_volume = float(trip.vehicle.max_volume_m3) if trip.vehicle.max_volume_m3 else (
        float(trip.vehicle.internal_length_mm) * float(trip.vehicle.internal_width_mm)
        * float(trip.vehicle.internal_height_mm) / 1_000_000_000
    )
    if known_weight > float(trip.vehicle.max_payload_kg) + 0.0001:
        raise ShipmentError("vehicle_payload_exceeded", "Known gross weight exceeds vehicle payload")
    if known_volume > vehicle_volume + 0.0001:
        raise ShipmentError("vehicle_volume_exceeded", "Known package volume exceeds vehicle volume")
    return {
        "package_count": len(items),
        "selected_weight_kg": round(known_weight, 4),
        "unknown_weight_count": unknown_weight,
        "remaining_payload_kg": round(float(trip.vehicle.max_payload_kg) - known_weight, 4),
        "selected_volume_m3": round(known_volume, 6),
        "unknown_volume_count": unknown_volume,
        "vehicle_volume_m3": round(vehicle_volume, 6),
        "remaining_volume_m3": round(vehicle_volume - known_volume, 6),
    }


def _movement(db: Session, item: MesShipmentItem, kind: str, actor: str, note: str) -> None:
    db.add(MesInventoryMovement(
        inventory_id=item.inventory_id,
        job_id=item.inventory.job_id,
        package_id=item.package_id,
        movement_type=kind,
        from_location_id=item.placement.location_id,
        to_location_id=item.placement.location_id,
        quantity=item.planned_quantity,
        performed_by=actor,
        notes=note,
    ))


def _touch_trip(trip: MesTrip, actor: str, *, force_loading: bool = False) -> None:
    if force_loading and trip.status == "loaded":
        trip.status = "loading"
    trip.version += 1
    trip.updated_by = actor
    trip.updated_at = datetime.utcnow()


def _rebuild_current_plan(db: Session, trip: MesTrip, actor: str) -> None:
    candidate = automatic_initial_plan(db, trip)
    if candidate["unplaced_item_ids"]:
        raise ShipmentError(
            "loading_plan_capacity_exceeded",
            "Corrected cargo does not fit the vehicle floor",
            context={"unplaced_item_ids": candidate["unplaced_item_ids"]},
        )
    db.query(MesLoadingPlanPlacement).filter_by(trip_id=trip.id).delete(synchronize_session=False)
    for raw in candidate["placements"]:
        db.add(MesLoadingPlanPlacement(
            trip_id=trip.id,
            shipment_item_id=raw["shipment_item_id"],
            x_mm=raw["x_mm"],
            y_mm=raw["y_mm"],
            placed_width_mm=raw["placed_width_mm"],
            placed_length_mm=raw["placed_length_mm"],
            rotation=raw["rotation"],
            loading_sequence=raw["loading_sequence"],
            created_by=actor,
            updated_by=actor,
        ))
    db.flush()


def unload_package(
    db: Session,
    trip_id: int,
    item_id: int,
    *,
    expected_trip_version: int,
    expected_item_version: int,
    reason: str,
    notes: str,
    idempotency_key: str,
    actor: str,
) -> dict:
    reason = _validate_reason(reason)
    payload = {
        "item_id": item_id, "expected_trip_version": expected_trip_version,
        "expected_item_version": expected_item_version, "reason": reason, "notes": notes.strip(),
    }
    existing = _existing(db, trip_id=trip_id, action="UNLOADED", key=idempotency_key, payload=payload)
    if existing is not None:
        return existing
    trip, item = _locked_trip_item(
        db, trip_id, item_id, expected_trip_version=expected_trip_version,
        expected_item_version=expected_item_version,
    )
    if item.assignment_status != "active" or item.loaded_quantity <= 0:
        raise ShipmentError("package_not_loaded", "Package is not currently loaded")
    hold = reason == "damaged_before_dispatch"
    item.loaded_quantity = 0
    item.assigned_quantity = 0
    item.assignment_status = "hold" if hold else "unloaded"
    item.version += 1
    item.updated_by = actor
    item.updated_at = datetime.utcnow()
    item.placement.status = "hold" if hold else "unloaded"
    item.placement.version += 1
    item.placement.updated_by = actor
    item.placement.updated_at = datetime.utcnow()
    item.inventory.status = "hold" if hold else "unloaded"
    item.inventory.updated_at = datetime.utcnow()
    db.query(MesLoadingPlanPlacement).filter_by(
        trip_id=trip.id, shipment_item_id=item.id,
    ).delete(synchronize_session=False)
    _movement(db, item, "trip_unload", actor, f"Trip {trip.trip_number}; reason={reason}")
    _touch_trip(trip, actor, force_loading=True)
    db.flush()
    result = {
        "trip_id": trip.id, "trip_status": trip.status, "trip_version": trip.version,
        "item": serialize_item(item), "capacity": capacity_summary(db, trip), "idempotent": False,
    }
    return _store(
        db, trip=trip, item=item, action="UNLOADED", reason=reason, notes=notes,
        key=idempotency_key, payload=payload, actor=actor, result=result,
    )


def return_to_warehouse(
    db: Session,
    trip_id: int,
    item_id: int,
    *,
    expected_trip_version: int,
    expected_item_version: int,
    reason: str,
    notes: str,
    idempotency_key: str,
    actor: str,
) -> dict:
    reason = _validate_reason(reason)
    payload = {
        "item_id": item_id, "expected_trip_version": expected_trip_version,
        "expected_item_version": expected_item_version, "reason": reason, "notes": notes.strip(),
    }
    existing = _existing(
        db, trip_id=trip_id, action="RETURNED_TO_WAREHOUSE", key=idempotency_key, payload=payload,
    )
    if existing is not None:
        return existing
    trip, item = _locked_trip_item(
        db, trip_id, item_id, expected_trip_version=expected_trip_version,
        expected_item_version=expected_item_version,
    )
    if item.assignment_status not in {"unloaded", "hold"}:
        raise ShipmentError("package_not_unloaded", "Unload the package before returning it")
    hold = item.assignment_status == "hold" or reason == "damaged_before_dispatch"
    item.assignment_status = "hold" if hold else "returned"
    item.version += 1
    item.updated_by = actor
    item.updated_at = datetime.utcnow()
    item.placement.status = "hold" if hold else "placed"
    item.placement.version += 1
    item.placement.updated_by = actor
    item.placement.updated_at = datetime.utcnow()
    item.inventory.status = "hold" if hold else "in_stock"
    item.inventory.updated_at = datetime.utcnow()
    _movement(db, item, "trip_return", actor, f"Trip {trip.trip_number}; reason={reason}")
    _touch_trip(trip, actor)
    db.flush()
    result = {
        "trip_id": trip.id, "trip_status": trip.status, "trip_version": trip.version,
        "available_to_ship": not hold, "item": serialize_item(item),
        "capacity": capacity_summary(db, trip), "idempotent": False,
    }
    return _store(
        db, trip=trip, item=item, action="RETURNED_TO_WAREHOUSE", reason=reason,
        notes=notes, key=idempotency_key, payload=payload, actor=actor, result=result,
    )


def reload_package(
    db: Session,
    trip_id: int,
    item_id: int,
    *,
    expected_trip_version: int,
    expected_item_version: int,
    reason: str,
    notes: str,
    idempotency_key: str,
    actor: str,
) -> dict:
    reason = _validate_reason(reason)
    payload = {
        "item_id": item_id, "expected_trip_version": expected_trip_version,
        "expected_item_version": expected_item_version, "reason": reason, "notes": notes.strip(),
    }
    existing = _existing(db, trip_id=trip_id, action="RELOADED", key=idempotency_key, payload=payload)
    if existing is not None:
        return existing
    trip, item = _locked_trip_item(
        db, trip_id, item_id, expected_trip_version=expected_trip_version,
        expected_item_version=expected_item_version,
    )
    if trip.status != "loading" or item.assignment_status not in {"unloaded", "returned"}:
        raise ShipmentError("package_not_reloadable", "Package is not ready to be reloaded")
    conflict = db.query(MesShipmentItem).filter(
        MesShipmentItem.package_id == item.package_id,
        MesShipmentItem.assignment_status == "active",
        MesShipmentItem.id != item.id,
    ).first()
    if conflict:
        raise ShipmentError("shipment_item_already_assigned", "Package belongs to another active trip")
    item.assignment_status = "active"
    item.assigned_quantity = item.planned_quantity
    item.loaded_quantity = item.planned_quantity
    item.version += 1
    item.updated_by = actor
    item.updated_at = datetime.utcnow()
    item.placement.status = "loaded"
    item.placement.version += 1
    item.placement.updated_by = actor
    item.placement.updated_at = datetime.utcnow()
    item.inventory.status = "loaded"
    item.inventory.updated_at = datetime.utcnow()
    capacity = capacity_summary(db, trip)
    _rebuild_current_plan(db, trip, actor)
    _movement(db, item, "trip_reload", actor, f"Trip {trip.trip_number}; reason={reason}")
    active = db.query(MesShipmentItem).filter_by(trip_id=trip.id, assignment_status="active").all()
    trip.status = "loaded" if active and all(
        abs(float(row.loaded_quantity) - float(row.assigned_quantity)) <= 0.0001 for row in active
    ) else "loading"
    _touch_trip(trip, actor)
    db.flush()
    result = {
        "trip_id": trip.id, "trip_status": trip.status, "trip_version": trip.version,
        "item": serialize_item(item), "capacity": capacity, "idempotent": False,
    }
    return _store(
        db, trip=trip, item=item, action="RELOADED", reason=reason, notes=notes,
        key=idempotency_key, payload=payload, actor=actor, result=result,
    )


def transfer_package(
    db: Session,
    trip_id: int,
    item_id: int,
    *,
    target_trip_id: int,
    expected_trip_version: int,
    expected_target_trip_version: int,
    expected_item_version: int,
    reason: str,
    notes: str,
    idempotency_key: str,
    actor: str,
) -> dict:
    reason = _validate_reason(reason)
    payload = {
        "item_id": item_id, "target_trip_id": target_trip_id,
        "expected_trip_version": expected_trip_version,
        "expected_target_trip_version": expected_target_trip_version,
        "expected_item_version": expected_item_version, "reason": reason, "notes": notes.strip(),
    }
    existing = _existing(db, trip_id=trip_id, action="TRANSFERRED", key=idempotency_key, payload=payload)
    if existing is not None:
        return existing
    source, item = _locked_trip_item(
        db, trip_id, item_id, expected_trip_version=expected_trip_version,
        expected_item_version=expected_item_version,
    )
    target = db.query(MesTrip).with_for_update().filter_by(id=target_trip_id).first()
    if not target:
        raise ShipmentError("target_trip_not_found", "Target trip not found", 404)
    if target.id == source.id:
        raise ShipmentError("target_trip_invalid", "Target trip must be different", 422)
    if target.version != expected_target_trip_version:
        raise ShipmentError("trip_version_conflict", "Target trip was changed", 409)
    if target.status not in {"planned", "loading"}:
        raise ShipmentError("target_trip_not_loadable", "Target trip does not accept loading")
    if item.assignment_status != "active" or item.loaded_quantity <= 0:
        raise ShipmentError("package_not_loaded", "Package is not currently loaded")
    conflict = db.query(MesShipmentItem).filter(
        MesShipmentItem.package_id == item.package_id,
        MesShipmentItem.assignment_status == "active",
        MesShipmentItem.id != item.id,
    ).first()
    if conflict:
        raise ShipmentError("shipment_item_already_assigned", "Package belongs to another active trip")
    item.assignment_status = "transferred"
    item.assigned_quantity = 0
    item.loaded_quantity = 0
    item.version += 1
    item.updated_by = actor
    item.updated_at = datetime.utcnow()
    item.placement.status = "assigned"
    item.placement.version += 1
    item.placement.updated_by = actor
    item.placement.updated_at = datetime.utcnow()
    item.inventory.status = "in_stock"
    item.inventory.updated_at = datetime.utcnow()
    db.query(MesLoadingPlanPlacement).filter_by(
        trip_id=source.id, shipment_item_id=item.id,
    ).delete(synchronize_session=False)
    target_item = MesShipmentItem(
        trip_id=target.id, dispatch_id=None, placement_id=item.placement_id,
        inventory_id=item.inventory_id, package_id=item.package_id,
        project_id=item.project_id, project_line_id=item.project_line_id,
        template_id=item.template_id, release_id=item.release_id,
        planned_quantity=item.planned_quantity, assigned_quantity=item.planned_quantity,
        loaded_quantity=0, gross_weight_kg=item.gross_weight_kg,
        length_mm=item.length_mm, width_mm=item.width_mm, height_mm=item.height_mm,
        assignment_status="active", created_by=actor, updated_by=actor,
    )
    db.add(target_item)
    db.flush()
    source_capacity = capacity_summary(db, source)
    target_capacity = capacity_summary(db, target)
    _movement(db, item, "trip_transfer_out", actor,
              f"Trip {source.trip_number} -> {target.trip_number}; reason={reason}")
    _touch_trip(source, actor, force_loading=True)
    _touch_trip(target, actor)
    db.flush()
    result = {
        "trip_id": source.id, "trip_status": source.status, "trip_version": source.version,
        "target_trip_id": target.id, "target_trip_status": target.status,
        "target_trip_version": target.version, "target_item": serialize_item(target_item),
        "source_capacity": source_capacity, "target_capacity": target_capacity,
        "idempotent": False,
    }
    return _store(
        db, trip=source, target_trip=target, item=item, target_item=target_item,
        action="TRANSFERRED", reason=reason, notes=notes, key=idempotency_key,
        payload=payload, actor=actor, result=result,
    )


def replace_package(
    db: Session,
    trip_id: int,
    item_id: int,
    *,
    replacement_placement_id: int,
    expected_trip_version: int,
    expected_item_version: int,
    expected_replacement_version: int,
    reason: str,
    notes: str,
    idempotency_key: str,
    actor: str,
) -> dict:
    reason = _validate_reason(reason)
    payload = {
        "item_id": item_id, "replacement_placement_id": replacement_placement_id,
        "expected_trip_version": expected_trip_version,
        "expected_item_version": expected_item_version,
        "expected_replacement_version": expected_replacement_version,
        "reason": reason, "notes": notes.strip(),
    }
    existing = _existing(db, trip_id=trip_id, action="REPLACED", key=idempotency_key, payload=payload)
    if existing is not None:
        return existing
    trip, item = _locked_trip_item(
        db, trip_id, item_id, expected_trip_version=expected_trip_version,
        expected_item_version=expected_item_version,
    )
    if item.assignment_status != "active" or item.loaded_quantity <= 0:
        raise ShipmentError("package_not_loaded", "Package is not currently loaded")
    replacement = db.query(MesFinishedGoodsPlacement).with_for_update().filter_by(
        id=replacement_placement_id,
    ).first()
    if not replacement:
        raise ShipmentError("replacement_not_found", "Replacement package was not found", 404)
    if replacement.version != expected_replacement_version:
        raise ShipmentError("replacement_version_conflict", "Replacement package changed", 409)
    replacement_inventory = replacement.inventory
    replacement_package = replacement.package
    if (
        replacement.status != "placed" or not replacement_inventory
        or replacement_inventory.status != "in_stock" or not replacement_package
        or replacement_package.status != "placed"
        or replacement.project_line_id != item.project_line_id
        or replacement.template_id != item.template_id
        or replacement.release_id != item.release_id
        or abs(float(replacement.quantity) - float(item.planned_quantity)) > 0.0001
    ):
        raise ShipmentError(
            "replacement_ineligible",
            "Replacement must be an available equivalent package from the same project line",
        )
    item.assignment_status = "replaced"
    item.assigned_quantity = 0
    item.loaded_quantity = 0
    item.version += 1
    item.updated_by = actor
    item.updated_at = datetime.utcnow()
    hold = reason == "damaged_before_dispatch"
    item.placement.status = "hold" if hold else "placed"
    item.placement.version += 1
    item.placement.updated_by = actor
    item.placement.updated_at = datetime.utcnow()
    item.inventory.status = "hold" if hold else "in_stock"
    item.inventory.updated_at = datetime.utcnow()
    gross = float(replacement_package.gross_weight_kg) if replacement_package.gross_weight_kg > 0 else None
    template = replacement_inventory.template
    dimensions = (template.length_mm, template.width_mm, template.height_mm)
    if not all(value is not None and float(value) > 0 for value in dimensions):
        dimensions = (None, None, None)
    target_item = MesShipmentItem(
        trip_id=trip.id, placement_id=replacement.id,
        inventory_id=replacement_inventory.id, package_id=replacement_package.id,
        project_id=replacement.project_id, project_line_id=replacement.project_line_id,
        template_id=replacement.template_id, release_id=replacement.release_id,
        planned_quantity=replacement.quantity, assigned_quantity=replacement.quantity,
        loaded_quantity=replacement.quantity, gross_weight_kg=gross,
        length_mm=dimensions[0], width_mm=dimensions[1], height_mm=dimensions[2],
        assignment_status="active", created_by=actor, updated_by=actor,
    )
    db.add(target_item)
    replacement.status = "loaded"
    replacement.version += 1
    replacement.updated_by = actor
    replacement.updated_at = datetime.utcnow()
    replacement_inventory.status = "loaded"
    replacement_inventory.updated_at = datetime.utcnow()
    db.flush()
    capacity_summary(db, trip)
    _rebuild_current_plan(db, trip, actor)
    _movement(db, item, "trip_unload", actor, f"Trip {trip.trip_number}; replacement; reason={reason}")
    _movement(db, target_item, "trip_load", actor, f"Trip {trip.trip_number}; replacement")
    active = db.query(MesShipmentItem).filter_by(trip_id=trip.id, assignment_status="active").all()
    trip.status = "loaded" if active and all(
        abs(float(row.loaded_quantity) - float(row.assigned_quantity)) <= 0.0001 for row in active
    ) else "loading"
    _touch_trip(trip, actor)
    db.flush()
    result = {
        "trip_id": trip.id, "trip_status": trip.status, "trip_version": trip.version,
        "source_item": serialize_item(item), "replacement_item": serialize_item(target_item),
        "capacity": capacity_summary(db, trip), "idempotent": False,
    }
    return _store(
        db, trip=trip, item=item, target_item=target_item,
        replacement_package_id=replacement_package.id, action="REPLACED",
        reason=reason, notes=notes, key=idempotency_key, payload=payload,
        actor=actor, result=result,
    )
