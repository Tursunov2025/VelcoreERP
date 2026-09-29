"""Authoritative MesTrip assignment, planning, SLA and GPS alert rules."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from models import MesTrip, MesTripLatestLocation, MesTripTrackingSession, MesVehicle, User, UserIdentityProfile
from services.audit import log_value_change
from services.trip_tracking import effective_health, gps_policy


CONFLICTING_TRIP_STATUSES = {"planned", "loading", "loaded", "dispatched", "in_transit", "arrived"}
ASSIGNABLE_TRIP_STATUSES = {"draft", "planned"}
PLANNABLE_TRIP_STATUSES = {"draft", "planned", "loading"}
TERMINAL_TRIP_STATUSES = {"delivered", "accepted", "cancelled"}
VEHICLE_STATES = {"AVAILABLE", "SERVICE", "INACTIVE"}


class LogisticsPlanningError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 409, **context):
        super().__init__(message)
        self.code, self.status_code, self.context = code, status_code, context


def _advisory_lock(db: Session, kind: int, value: int | None) -> None:
    if value is not None and db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:kind, :value)"), {"kind": kind, "value": value})


def _conflict(db: Session, trip: MesTrip, field: str, value: int | None) -> MesTrip | None:
    if value is None:
        return None
    return db.query(MesTrip).filter(
        MesTrip.id != trip.id,
        getattr(MesTrip, field) == value,
        MesTrip.status.in_(CONFLICTING_TRIP_STATUSES),
    ).order_by(MesTrip.id).first()


def _driver_snapshot(db: Session, user: User | None) -> tuple[str, str]:
    if not user:
        return "", ""
    profile = db.query(UserIdentityProfile).filter_by(user_id=user.id).first()
    return ((profile.full_name if profile else "") or user.username, (profile.phone if profile else "") or "")


def update_trip_assignment(db: Session, trip_id: int, *, vehicle_id: int | None,
                           driver_user_id: int | None, expected_version: int, actor: str) -> MesTrip:
    trip = db.query(MesTrip).with_for_update().filter_by(id=trip_id).first()
    if not trip:
        raise LogisticsPlanningError("trip_not_found", "Trip not found", 404)
    if trip.version != expected_version:
        raise LogisticsPlanningError("trip_version_conflict", "Trip was changed", 409)
    if trip.status not in ASSIGNABLE_TRIP_STATUSES:
        raise LogisticsPlanningError("trip_assignment_locked", "Trip assignment is locked for this lifecycle state")
    _advisory_lock(db, 7101, vehicle_id)
    _advisory_lock(db, 7102, driver_user_id)
    vehicle = db.get(MesVehicle, vehicle_id) if vehicle_id is not None else None
    if vehicle_id is not None and not vehicle:
        raise LogisticsPlanningError("vehicle_not_found", "Vehicle not found", 404)
    if vehicle and (not vehicle.is_active or vehicle.operational_state != "AVAILABLE"):
        raise LogisticsPlanningError("vehicle_not_available", "Vehicle is not operationally available", vehicle_state=vehicle.operational_state)
    driver = db.query(User).filter_by(id=driver_user_id, role="driver", is_active=True).first() if driver_user_id is not None else None
    if driver_user_id is not None and not driver:
        raise LogisticsPlanningError("driver_not_available", "Active Driver user not found", 404)
    vehicle_conflict = _conflict(db, trip, "vehicle_id", vehicle_id)
    if vehicle_conflict:
        raise LogisticsPlanningError("vehicle_assignment_conflict", "Vehicle has a conflicting active trip", conflicting_trip_id=vehicle_conflict.id, conflicting_trip_number=vehicle_conflict.trip_number)
    driver_conflict = _conflict(db, trip, "driver_user_id", driver_user_id)
    if driver_conflict:
        raise LogisticsPlanningError("driver_assignment_conflict", "Driver has a conflicting active trip", conflicting_trip_id=driver_conflict.id, conflicting_trip_number=driver_conflict.trip_number)
    old_vehicle, old_driver = trip.vehicle_id, trip.driver_user_id
    trip.vehicle_id, trip.driver_user_id = vehicle_id, driver_user_id
    trip.driver_name_snapshot, trip.driver_phone_snapshot = _driver_snapshot(db, driver)
    trip.version += 1
    trip.updated_by, trip.updated_at = actor, datetime.utcnow()
    if old_vehicle != vehicle_id:
        log_value_change(db, actor, "assignment", "mes_trip", trip.id, "vehicle_id", old_vehicle, vehicle_id)
    if old_driver != driver_user_id:
        log_value_change(db, actor, "assignment", "mes_trip", trip.id, "driver_user_id", old_driver, driver_user_id)
    db.flush()
    return trip


def update_trip_plan(db: Session, trip_id: int, *, planned_loading_at: datetime | None,
                     planned_departure_at: datetime | None, delivery_deadline_at: datetime | None,
                     expected_version: int, actor: str) -> MesTrip:
    trip = db.query(MesTrip).with_for_update().filter_by(id=trip_id).first()
    if not trip:
        raise LogisticsPlanningError("trip_not_found", "Trip not found", 404)
    if trip.version != expected_version:
        raise LogisticsPlanningError("trip_version_conflict", "Trip was changed", 409)
    if trip.status not in PLANNABLE_TRIP_STATUSES:
        raise LogisticsPlanningError("trip_planning_locked", "Terminal or dispatched trip cannot be replanned")
    values = [planned_loading_at, planned_departure_at, delivery_deadline_at]
    values = [value.replace(tzinfo=None) if value and value.tzinfo else value for value in values]
    loading, departure, deadline = values
    if loading and departure and departure < loading:
        raise LogisticsPlanningError("departure_before_loading", "Planned departure cannot precede loading", 422)
    if departure and deadline and deadline < departure:
        raise LogisticsPlanningError("deadline_before_departure", "Delivery deadline cannot precede departure", 422)
    for field, value in zip(("planned_loading_at", "planned_departure_at", "delivery_deadline_at"), values):
        old = getattr(trip, field)
        if old != value:
            setattr(trip, field, value)
            log_value_change(db, actor, "planning", "mes_trip", trip.id, field, old, value)
    trip.version += 1
    trip.updated_by, trip.updated_at = actor, datetime.utcnow()
    db.flush()
    return trip


def update_vehicle_state(db: Session, vehicle_id: int, *, operational_state: str,
                         expected_version: int, actor: str) -> MesVehicle:
    vehicle = db.query(MesVehicle).with_for_update().filter_by(id=vehicle_id).first()
    if not vehicle:
        raise LogisticsPlanningError("vehicle_not_found", "Vehicle not found", 404)
    if vehicle.version != expected_version:
        raise LogisticsPlanningError("vehicle_version_conflict", "Vehicle was changed")
    state = operational_state.upper()
    if state not in VEHICLE_STATES:
        raise LogisticsPlanningError("invalid_vehicle_state", "Invalid vehicle operational state", 422)
    active = db.query(MesTrip).filter(MesTrip.vehicle_id == vehicle.id, MesTrip.status.in_(CONFLICTING_TRIP_STATUSES)).first()
    if state != "AVAILABLE" and active:
        raise LogisticsPlanningError("vehicle_active_trip_conflict", "Vehicle has a conflicting active trip", conflicting_trip_id=active.id, conflicting_trip_number=active.trip_number)
    old = vehicle.operational_state
    vehicle.operational_state = state
    vehicle.is_active = state != "INACTIVE"
    vehicle.version += 1
    vehicle.updated_by, vehicle.updated_at = actor, datetime.utcnow()
    log_value_change(db, actor, "operational_state", "mes_vehicle", vehicle.id, "operational_state", old, state)
    db.flush()
    return vehicle


def sla_state(trip: MesTrip, now: datetime | None = None) -> str:
    if not trip.delivery_deadline_at:
        return "deadline_unavailable"
    deadline = trip.delivery_deadline_at.replace(tzinfo=None)
    arrival = trip.arrived_at.replace(tzinfo=None) if trip.arrived_at else None
    if arrival:
        return "delivered_late" if arrival > deadline else "delivered_on_time"
    if trip.status in {"accepted", "cancelled"}:
        return "not_applicable"
    return "delayed" if (now or datetime.utcnow()) > deadline else "on_schedule"


def derive_trip_alerts(db: Session, trip: MesTrip, now: datetime | None = None) -> list[dict]:
    now = now or datetime.utcnow()
    alerts = []
    if sla_state(trip, now) == "delayed":
        alerts.append({"type": "TRIP_DELAYED", "severity": "high", "trip_id": trip.id})
    if trip.status == "loaded":
        alerts.append({"type": "READY_TO_DISPATCH", "severity": "medium", "trip_id": trip.id})
    if trip.status == "in_transit":
        alerts.append({"type": "ARRIVAL_CONFIRMATION_PENDING", "severity": "medium", "trip_id": trip.id})
    if trip.status == "arrived":
        alerts.append({"type": "DELIVERY_CONFIRMATION_PENDING", "severity": "high", "trip_id": trip.id})
    if trip.status in CONFLICTING_TRIP_STATUSES:
        session = db.query(MesTripTrackingSession).filter_by(trip_id=trip.id, status="active").order_by(MesTripTrackingSession.id.desc()).first()
        latest = db.get(MesTripLatestLocation, trip.id)
        if not session or not latest:
            alerts.append({"type": "DISPATCHED_NO_GPS" if trip.status == "dispatched" else "VEHICLE_WITH_ACTIVE_TRIP_NO_GPS", "severity": "high", "trip_id": trip.id})
        elif effective_health(session, gps_policy(db), now) == "stale":
            alerts.append({"type": "GPS_STALE_SIGNAL", "severity": "medium", "trip_id": trip.id})
        elif session.health_state == "offline":
            alerts.append({"type": "GPS_OFFLINE", "severity": "medium", "trip_id": trip.id})
    return alerts
