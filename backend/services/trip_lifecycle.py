"""Canonical MesTrip lifecycle rules and non-inventory transition orchestration."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from models import MesTrip, MesTripCommand, MesTripLocation
from services.audit import log_action, log_value_change


TRIP_TRANSITIONS = {
    "draft": {"planned", "cancelled"},
    "planned": {"loading", "cancelled"},
    "loading": {"loaded", "cancelled"},
    "loaded": {"dispatched", "cancelled"},
    "dispatched": {"in_transit", "delivery_exception"},
    "in_transit": {"arrived", "delivery_exception"},
    "arrived": {"delivered", "delivery_exception"},
    "delivery_exception": {"in_transit", "arrived", "delivered", "cancelled"},
    "delivered": {"accepted", "delivery_exception"},
    "accepted": set(),
    "cancelled": set(),
}
TERMINAL_TRIP_STATUSES = {"accepted", "cancelled"}


class TripLifecycleError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def require_transition(source: str, target: str) -> None:
    if target not in TRIP_TRANSITIONS.get(source, set()):
        raise TripLifecycleError("invalid_trip_transition", f"Cannot transition from {source} to {target}")


def _payload_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def confirm_arrival(db: Session, trip_id: int, *, expected_version: int,
                    idempotency_key: str, actor: str) -> dict:
    payload = {"expected_version": expected_version}
    digest = _payload_hash(payload)
    prior = db.query(MesTripCommand).filter_by(idempotency_key=idempotency_key).first()
    if prior:
        if prior.trip_id != trip_id or prior.command_type != "confirm_arrival" or prior.payload_hash != digest:
            raise TripLifecycleError("idempotency_conflict", "Idempotency key belongs to another command")
        return {**prior.result_json, "idempotent": True}
    trip = db.query(MesTrip).with_for_update().filter_by(id=trip_id).first()
    if not trip:
        raise TripLifecycleError("trip_not_found", "Trip not found", 404)
    if trip.version != expected_version:
        raise TripLifecycleError("trip_version_conflict", "Trip was changed")
    require_transition(trip.status, "arrived")
    now = datetime.utcnow()
    changed = db.execute(update(MesTrip).where(
        MesTrip.id == trip.id, MesTrip.status == "in_transit", MesTrip.version == expected_version,
    ).values(status="arrived", arrived_at=now, version=expected_version + 1,
             updated_by=actor, updated_at=now)).rowcount
    if changed != 1:
        raise TripLifecycleError("arrival_state_conflict", "Arrival was confirmed concurrently")
    result = {"trip_id": trip.id, "status": "arrived", "trip_version": expected_version + 1,
              "arrived_at": now.isoformat(), "idempotent": False}
    db.add(MesTripCommand(trip_id=trip.id, command_type="confirm_arrival",
                          idempotency_key=idempotency_key, payload_hash=digest,
                          result_json=result, actor=actor))
    log_value_change(db, actor, "status", "mes_trip", trip.id, "status", "in_transit", "arrived")
    log_action(db, actor, "arrival_confirmed", "mes_trip", trip.id, "manual authoritative arrival")
    db.flush()
    return result


def evaluate_gps_in_transit(db: Session, point: MesTripLocation) -> bool:
    """Promote dispatched to in_transit from a newly accepted post-dispatch point."""
    trip = db.query(MesTrip).with_for_update().filter_by(id=point.trip_id).first()
    if not trip or trip.status != "dispatched" or not trip.actual_departure_at:
        return False
    captured = point.captured_at.replace(tzinfo=None)
    received = point.received_at.replace(tzinfo=None)
    departure = trip.actual_departure_at.replace(tzinfo=None)
    if captured < departure or received < departure:
        return False
    changed = db.execute(update(MesTrip).where(
        MesTrip.id == trip.id, MesTrip.status == "dispatched", MesTrip.version == trip.version,
    ).values(status="in_transit", version=trip.version + 1,
             updated_by="gps-lifecycle", updated_at=datetime.utcnow())).rowcount
    if changed != 1:
        return False
    log_value_change(db, "gps-lifecycle", "status", "mes_trip", trip.id,
                     "status", "dispatched", "in_transit")
    log_action(db, "gps-lifecycle", "gps_in_transit", "mes_trip", trip.id,
               f"session={point.session_id}; point={point.id}")
    db.flush()
    return True


def automatic_arrival_readiness(_trip: MesTrip) -> dict:
    """Level-B contract: intentionally disabled until destination coordinates are authoritative."""
    return {"enabled": False, "reason": "authoritative_destination_coordinates_unavailable"}
