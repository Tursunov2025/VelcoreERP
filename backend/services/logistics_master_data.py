"""Authoritative Logistics master-data operations.

Vehicles remain MesVehicle rows and drivers remain User(role=driver) plus
UserIdentityProfile.  GPS devices are identities bound to those records; a
tracking session is still the operational source for trip history.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.security import hash_password
from models import MesGpsDevice, MesTrip, MesTripTrackingSession, MesVehicle, User, UserIdentityActivity, UserIdentityProfile
from services.audit import log_action, log_value_change
from services.finished_logistics import LogisticsError


ACTIVE_TRIP_STATUSES = ("planned", "loading", "loaded", "dispatched", "in_transit", "arrived")


def _clean(value) -> str:
    return str(value or "").strip()


def _profile(db: Session, user_id: int) -> UserIdentityProfile:
    row = db.query(UserIdentityProfile).filter_by(user_id=user_id).first()
    if not row:
        row = UserIdentityProfile(user_id=user_id)
        db.add(row)
        db.flush()
    return row


def serialize_driver(db: Session, user: User) -> dict:
    profile = db.query(UserIdentityProfile).filter_by(user_id=user.id).first()
    active_trip = db.query(MesTrip).filter(
        MesTrip.driver_user_id == user.id,
        MesTrip.status.in_(ACTIVE_TRIP_STATUSES),
    ).order_by(MesTrip.id.desc()).first()
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "department": user.department,
        "is_active": bool(user.is_active),
        "created_at": user.created_at,
        "full_name": profile.full_name if profile else "",
        "employee_id": profile.employee_id if profile else "",
        "position": profile.position if profile else "",
        "phone": profile.phone if profile else "",
        "email": profile.email if profile else "",
        "telegram": profile.telegram if profile else "",
        "avatar_url": profile.avatar_url if profile else "",
        "last_login_at": profile.last_login_at if profile else None,
        "active_trip_id": active_trip.id if active_trip else None,
        "active_trip_number": active_trip.trip_number if active_trip else None,
        "active_vehicle_id": active_trip.vehicle_id if active_trip else None,
    }


def create_driver(db: Session, data, actor: str) -> User:
    username = _clean(data.username)
    if db.query(User).filter(User.username == username).first():
        raise LogisticsError("driver_username_exists", "Username already exists", 409)
    password = _clean(data.password)
    if len(password) < 8:
        raise LogisticsError("driver_password_required", "A driver password of at least 8 characters is required", 422)
    user = User(
        username=username,
        password_hash=hash_password(password),
        password=None,
        role="driver",
        department=_clean(data.department),
        is_active=bool(data.is_active),
    )
    db.add(user)
    db.flush()
    profile = _profile(db, user.id)
    for field in ("full_name", "employee_id", "position", "phone", "email", "telegram", "avatar_url"):
        setattr(profile, field, _clean(getattr(data, field, "")))
    db.add(UserIdentityActivity(user_id=user.id, action="created", actor_username=actor, details="Canonical Logistics driver"))
    log_action(db, actor, "create", "driver", user.id, "canonical logistics driver")
    return user


def update_driver(db: Session, user_id: int, data, actor: str) -> User:
    user = db.query(User).with_for_update().filter_by(id=user_id, role="driver").first()
    if not user:
        raise LogisticsError("driver_not_found", "Driver not found", 404)
    if user.username == actor and getattr(data, "is_active", None) is False:
        raise LogisticsError("self_lockout", "You cannot deactivate your own account", 409)
    username = _clean(data.username)
    duplicate = db.query(User).filter(User.username == username, User.id != user.id).first()
    if duplicate:
        raise LogisticsError("driver_username_exists", "Username already exists", 409)
    if hasattr(data, "is_active") and data.is_active is False and user.is_active:
        active = db.query(MesTrip).filter(MesTrip.driver_user_id == user.id, MesTrip.status.in_(ACTIVE_TRIP_STATUSES)).first()
        if active:
            raise LogisticsError("driver_active_trip_conflict", "Driver has a conflicting active trip", 409)
    user.username = username
    user.department = _clean(data.department)
    if hasattr(data, "is_active") and data.is_active is not None:
        user.is_active = bool(data.is_active)
    password = _clean(getattr(data, "password", ""))
    if password:
        if len(password) < 8:
            raise LogisticsError("driver_password_invalid", "A driver password must contain at least 8 characters", 422)
        user.password_hash = hash_password(password)
        user.password = None
    profile = _profile(db, user.id)
    for field in ("full_name", "employee_id", "position", "phone", "email", "telegram", "avatar_url"):
        value = getattr(data, field, None)
        if value is not None:
            setattr(profile, field, _clean(value))
    db.add(UserIdentityActivity(user_id=user.id, action="updated", actor_username=actor, details="Canonical Logistics driver"))
    log_action(db, actor, "update", "driver", user.id, "canonical logistics driver")
    db.flush()
    return user


def set_driver_status(db: Session, user_id: int, active: bool, actor: str) -> User:
    user = db.query(User).with_for_update().filter_by(id=user_id, role="driver").first()
    if not user:
        raise LogisticsError("driver_not_found", "Driver not found", 404)
    if user.username == actor and not active:
        raise LogisticsError("self_lockout", "You cannot deactivate your own account", 409)
    if not active and user.is_active:
        trip = db.query(MesTrip).filter(MesTrip.driver_user_id == user.id, MesTrip.status.in_(ACTIVE_TRIP_STATUSES)).first()
        if trip:
            raise LogisticsError("driver_active_trip_conflict", "Driver has a conflicting active trip", 409)
    user.is_active = bool(active)
    db.add(UserIdentityActivity(user_id=user.id, action="activated" if active else "deactivated", actor_username=actor, details="Canonical Logistics driver"))
    log_action(db, actor, "activate" if active else "deactivate", "driver", user.id, "canonical logistics driver")
    db.flush()
    return user


def _device_identifier(value: str) -> str:
    # Device identities are case-insensitive in practice; keeping a stable
    # uppercase key prevents duplicate bindings after reconnect.
    key = _clean(value).upper()
    if not key or len(key) > 180:
        raise LogisticsError("invalid_gps_device", "GPS device identity is required", 422)
    return key


def _device_status(value: str | None, default: str = "active") -> str:
    status = _clean(value or default).lower()
    if status not in {"active", "inactive"}:
        raise LogisticsError("invalid_gps_device_status", "GPS device status is invalid", 422)
    return status


def _device_protocol(value: str | None, default: str = "custom_http") -> str:
    protocol = _clean(value or default).lower()
    if protocol not in {"custom_http", "teltonika_avl", "sinotrack_h02"}:
        raise LogisticsError("invalid_gps_device_protocol", "GPS device protocol is invalid", 422)
    return protocol


def serialize_device(row: MesGpsDevice) -> dict:
    return {
        "id": row.id,
        "device_identifier": row.device_identifier,
        "vehicle_id": row.vehicle_id,
        "driver_user_id": row.driver_user_id,
        "status": row.status,
        "protocol": row.protocol,
        "notes": row.notes or "",
        "version": row.version,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _validate_device_scope(db: Session, vehicle_id: int, driver_user_id: int | None):
    vehicle = db.query(MesVehicle).filter_by(id=vehicle_id).first()
    if not vehicle:
        raise LogisticsError("vehicle_not_found", "Vehicle not found", 404)
    if not vehicle.is_active or vehicle.operational_state == "INACTIVE":
        raise LogisticsError("vehicle_not_available", "GPS cannot be bound to an inactive vehicle", 409)
    if driver_user_id is not None:
        driver = db.query(User).filter_by(id=driver_user_id, role="driver", is_active=True).first()
        if not driver:
            raise LogisticsError("driver_not_available", "Active driver user not found", 404)
    return vehicle


def create_gps_device(db: Session, data, actor: str) -> MesGpsDevice:
    identifier = _device_identifier(data.device_identifier)
    _validate_device_scope(db, data.vehicle_id, data.driver_user_id)
    if db.query(MesGpsDevice).filter_by(device_identifier=identifier).first():
        raise LogisticsError("gps_device_exists", "GPS device is already bound", 409)
    row = MesGpsDevice(
        device_identifier=identifier,
        vehicle_id=data.vehicle_id,
        driver_user_id=data.driver_user_id,
        status=_device_status(getattr(data, "status", "active")),
        protocol=_device_protocol(getattr(data, "protocol", "custom_http")),
        notes=_clean(getattr(data, "notes", "")),
        created_by=actor,
        updated_by=actor,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        raise LogisticsError("gps_device_exists", "GPS device is already bound", 409) from exc
    log_action(db, actor, "bind", "mes_gps_device", row.id, f"vehicle={row.vehicle_id};driver={row.driver_user_id}")
    return row


def update_gps_device(db: Session, device_id: int, data, actor: str) -> MesGpsDevice:
    row = db.query(MesGpsDevice).with_for_update().filter_by(id=device_id).first()
    if not row:
        raise LogisticsError("gps_device_not_found", "GPS device not found", 404)
    if row.version != data.expected_version:
        raise LogisticsError("gps_device_version_conflict", "GPS device binding was changed", 409)
    vehicle_id = getattr(data, "vehicle_id", row.vehicle_id)
    driver_user_id = getattr(data, "driver_user_id", row.driver_user_id)
    _validate_device_scope(db, vehicle_id, driver_user_id)
    identifier = _device_identifier(getattr(data, "device_identifier", row.device_identifier))
    duplicate = db.query(MesGpsDevice).filter(MesGpsDevice.device_identifier == identifier, MesGpsDevice.id != row.id).first()
    if duplicate:
        raise LogisticsError("gps_device_exists", "GPS device is already bound", 409)
    active_session = db.query(MesTripTrackingSession).filter(MesTripTrackingSession.device_id == row.id, MesTripTrackingSession.status == "active").first()
    if active_session and (vehicle_id != row.vehicle_id or driver_user_id != row.driver_user_id):
        raise LogisticsError("gps_device_active_session", "Cannot rebind a device with an active tracking session", 409)
    old_vehicle, old_driver = row.vehicle_id, row.driver_user_id
    row.device_identifier = identifier
    row.vehicle_id, row.driver_user_id = vehicle_id, driver_user_id
    row.status = _device_status(getattr(data, "status", row.status), row.status)
    row.protocol = _device_protocol(getattr(data, "protocol", row.protocol), row.protocol)
    row.notes = _clean(getattr(data, "notes", row.notes))
    row.version += 1
    row.updated_by, row.updated_at = actor, datetime.utcnow()
    if old_vehicle != row.vehicle_id:
        log_value_change(db, actor, "bind", "mes_gps_device", row.id, "vehicle_id", old_vehicle, row.vehicle_id)
    if old_driver != row.driver_user_id:
        log_value_change(db, actor, "bind", "mes_gps_device", row.id, "driver_user_id", old_driver, row.driver_user_id)
    log_action(db, actor, "update", "mes_gps_device", row.id, "canonical GPS binding")
    db.flush()
    return row


def unbind_gps_device(db: Session, device_id: int, expected_version: int, actor: str) -> MesGpsDevice:
    row = db.query(MesGpsDevice).with_for_update().filter_by(id=device_id).first()
    if not row:
        raise LogisticsError("gps_device_not_found", "GPS device not found", 404)
    if row.version != expected_version:
        raise LogisticsError("gps_device_version_conflict", "GPS device binding was changed", 409)
    active_session = db.query(MesTripTrackingSession).filter(MesTripTrackingSession.device_id == row.id, MesTripTrackingSession.status == "active").first()
    if active_session:
        raise LogisticsError("gps_device_active_session", "Stop the active tracking session before unbinding", 409)
    row.status = "inactive"
    row.version += 1
    row.updated_by, row.updated_at = actor, datetime.utcnow()
    log_action(db, actor, "unbind", "mes_gps_device", row.id, "canonical GPS binding removed")
    db.flush()
    return row
