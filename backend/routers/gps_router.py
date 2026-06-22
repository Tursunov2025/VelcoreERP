"""Phase 12 — GPS Fleet Tracking API."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from auth.deps import get_current_user
from database import get_db
from models import Driver, GpsLocation, Transport, TransportTask, TripRoute, User, Vehicle
from services.audit import log_action
from services.gps_fleet import (
    build_dashboard,
    latest_locations_by_vehicle,
    save_location,
    serialize_location,
)
from services.gps_alerts import mark_vehicle_online
from services.permissions import user_has_permission

router = APIRouter(prefix="/gps", tags=["gps"])

TRIP_STATUSES = ["Planned", "Active", "In Transit", "Completed", "Cancelled"]
VEHICLE_STATUSES = ["active", "inactive", "maintenance"]
DRIVER_STATUSES = ["active", "inactive", "on_trip"]


def _can_view(db: Session, user: User) -> bool:
    return user.role == "admin" or user_has_permission(db, user, "export_view")


def _can_manage(db: Session, user: User) -> bool:
    return user.role == "admin" or user_has_permission(db, user, "export_manage")


def _can_read_fleet(db: Session, user: User) -> bool:
    """Admin panel + driver mobile — operators can read fleet lists."""
    if user.role in ("admin", "operator"):
        return True
    return _can_view(db, user)


class VehicleIn(BaseModel):
    plate_number: str
    model: str = ""
    status: Literal["active", "inactive", "maintenance"] = "active"


class DriverIn(BaseModel):
    full_name: str
    phone: str = ""
    telegram_username: str = ""
    status: Literal["active", "inactive", "on_trip"] = "active"


class LocationUpdateIn(BaseModel):
    vehicle_id: int
    driver_id: int | None = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    speed: float = Field(default=0, ge=0)
    battery_level: float | None = Field(default=None, ge=0, le=100)


class TripIn(BaseModel):
    transport_id: int | None = None
    vehicle_id: int
    driver_id: int | None = None
    origin: str = ""
    destination: str = ""
    status: Literal["Planned", "Active", "In Transit", "Completed", "Cancelled"] = "Planned"


class TransportTaskIn(BaseModel):
    title: str
    description: str = ""
    vehicle_id: int | None = None
    driver_id: int | None = None
    transport_id: int | None = None
    origin: str = ""
    destination: str = ""
    status: Literal["assigned", "active", "completed", "cancelled"] = "assigned"


class TransportTaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    vehicle_id: int | None = None
    driver_id: int | None = None
    transport_id: int | None = None
    origin: str | None = None
    destination: str | None = None
    status: Literal["assigned", "active", "completed", "cancelled"] | None = None


def _serialize_vehicle(v: Vehicle, loc: GpsLocation | None = None) -> dict:
    return {
        "id": v.id,
        "plate_number": v.plate_number,
        "model": v.model,
        "status": v.status,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "latest_location": serialize_location(loc),
    }


def _serialize_driver(d: Driver, loc: GpsLocation | None = None) -> dict:
    return {
        "id": d.id,
        "full_name": d.full_name,
        "phone": d.phone,
        "telegram_username": d.telegram_username,
        "status": d.status,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "latest_location": serialize_location(loc) if loc else None,
    }


def _serialize_trip(t: TripRoute) -> dict:
    return {
        "id": t.id,
        "transport_id": t.transport_id,
        "vehicle_id": t.vehicle_id,
        "driver_id": t.driver_id,
        "origin": t.origin,
        "destination": t.destination,
        "status": t.status,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "vehicle_plate": t.vehicle.plate_number if t.vehicle else None,
        "driver_name": t.driver.full_name if t.driver else None,
    }


def _serialize_transport_task(
    task: TransportTask,
    loc: GpsLocation | None = None,
) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description or "",
        "vehicle_id": task.vehicle_id,
        "driver_id": task.driver_id,
        "transport_id": task.transport_id,
        "origin": task.origin,
        "destination": task.destination,
        "status": task.status,
        "tracking_active": bool(task.tracking_active),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_by": task.created_by,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "vehicle_plate": task.vehicle.plate_number if task.vehicle else None,
        "driver_name": task.driver.full_name if task.driver else None,
        "latest_location": serialize_location(loc),
    }


@router.get("/vehicles")
def list_vehicles(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_read_fleet(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    latest = latest_locations_by_vehicle(db)
    vehicles = db.query(Vehicle).order_by(Vehicle.plate_number).all()
    return {
        "vehicles": [_serialize_vehicle(v, latest.get(v.id)) for v in vehicles],
    }


@router.post("/vehicles")
def create_vehicle(
    payload: VehicleIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_manage(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    plate = payload.plate_number.strip().upper()
    if not plate:
        raise HTTPException(status_code=400, detail="plate_number required")
    existing = db.query(Vehicle).filter(Vehicle.plate_number == plate).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vehicle already exists")
    vehicle = Vehicle(plate_number=plate, model=payload.model.strip(), status=payload.status)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    log_action(db, user.username, "gps_vehicle_create", plate)
    return _serialize_vehicle(vehicle, None)


@router.get("/drivers")
def list_drivers(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_read_fleet(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    drivers = db.query(Driver).order_by(Driver.full_name).all()
    result = []
    for d in drivers:
        loc = (
            db.query(GpsLocation)
            .filter(GpsLocation.driver_id == d.id)
            .order_by(desc(GpsLocation.recorded_at))
            .first()
        )
        result.append(_serialize_driver(d, loc))
    return {"drivers": result}


@router.post("/drivers")
def create_driver(
    payload: DriverIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_manage(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    name = payload.full_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="full_name required")
    driver = Driver(
        full_name=name,
        phone=payload.phone.strip(),
        telegram_username=payload.telegram_username.strip().lstrip("@"),
        status=payload.status,
    )
    db.add(driver)
    db.commit()
    db.refresh(driver)
    log_action(db, user.username, "gps_driver_create", name)
    return _serialize_driver(driver, None)


def _normalize_plate(raw: str) -> str:
    return " ".join(raw.strip().upper().split())


@router.get("/suggestions/transports")
def transport_suggestions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Transports whose vehicle/driver text is not yet in GPS fleet tables."""
    if not _can_view(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    existing_plates = {
        v.plate_number.upper()
        for v in db.query(Vehicle.plate_number).all()
    }
    existing_driver_names = {
        d.full_name.strip().lower()
        for d in db.query(Driver.full_name).all()
    }
    suggestions = []
    seen_plates: set[str] = set()
    for t in db.query(Transport).order_by(desc(Transport.created_at)).all():
        plate = _normalize_plate(t.vehicle or "")
        if not plate or plate in existing_plates or plate in seen_plates:
            continue
        seen_plates.add(plate)
        driver_name = (t.driver_name or "").strip()
        suggestions.append(
            {
                "transport_id": t.id,
                "plate_number": plate,
                "model": "",
                "driver_name": driver_name,
                "driver_phone": (t.driver_phone or "").strip(),
                "driver_exists": driver_name.lower() in existing_driver_names,
                "transport_status": t.status,
            }
        )
    return {"suggestions": suggestions}


@router.post("/import/from-transports")
def import_from_transports(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create GPS vehicles/drivers from legacy transport free-text fields."""
    if not _can_manage(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    existing_plates = {
        v.plate_number.upper(): v for v in db.query(Vehicle).all()
    }
    existing_drivers = {
        d.full_name.strip().lower(): d for d in db.query(Driver).all()
    }
    vehicles_created = 0
    drivers_created = 0
    for t in db.query(Transport).all():
        plate = _normalize_plate(t.vehicle or "")
        if plate and plate not in existing_plates:
            v = Vehicle(plate_number=plate, model="", status="active")
            db.add(v)
            db.flush()
            existing_plates[plate] = v
            vehicles_created += 1
        name = (t.driver_name or "").strip()
        if name and name.lower() not in existing_drivers:
            d = Driver(
                full_name=name,
                phone=(t.driver_phone or "").strip(),
                status="active",
            )
            db.add(d)
            db.flush()
            existing_drivers[name.lower()] = d
            drivers_created += 1
    db.commit()
    log_action(
        db,
        user.username,
        "gps_import_transports",
        f"vehicles={vehicles_created} drivers={drivers_created}",
    )
    return {
        "vehicles_created": vehicles_created,
        "drivers_created": drivers_created,
        "vehicles": db.query(Vehicle).count(),
        "drivers": db.query(Driver).count(),
    }


@router.post("/location/update")
def update_location(
    payload: LocationUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """GPS ping from driver mobile — any authenticated user."""
    vehicle = db.query(Vehicle).filter(Vehicle.id == payload.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if payload.driver_id is not None:
        driver = db.query(Driver).filter(Driver.id == payload.driver_id).first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        driver.status = "on_trip"

    loc, saved = save_location(
        db,
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed=payload.speed,
        battery_level=payload.battery_level,
    )
    mark_vehicle_online(db, payload.vehicle_id)
    db.commit()
    db.refresh(loc)

    if saved:
        log_action(
            db,
            user.username,
            "gps_location_update",
            f"vehicle={payload.vehicle_id} lat={payload.latitude}",
        )

    result = serialize_location(loc) or {}
    result["saved"] = saved
    if not saved:
        result["duplicate_skipped"] = True
    return result


@router.post("/update")
def gps_update_alias(
    payload: LocationUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Alias for POST /gps/location/update (driver mobile)."""
    return update_location(payload, db, user)


@router.get("/location/latest")
def latest_locations(
    vehicle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_read_fleet(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")

    if vehicle_id is not None:
        loc = (
            db.query(GpsLocation)
            .options(joinedload(GpsLocation.vehicle), joinedload(GpsLocation.driver))
            .filter(GpsLocation.vehicle_id == vehicle_id)
            .order_by(desc(GpsLocation.recorded_at))
            .first()
        )
        if not loc:
            return {"locations": []}
        return {
            "locations": [
                {
                    **serialize_location(loc),
                    "plate_number": loc.vehicle.plate_number if loc.vehicle else None,
                    "driver_name": loc.driver.full_name if loc.driver else None,
                }
            ]
        }

    latest = latest_locations_by_vehicle(db)
    vehicles = {v.id: v for v in db.query(Vehicle).all()}
    drivers = {d.id: d for d in db.query(Driver).all()}
    rows = []
    for vid, loc in latest.items():
        v = vehicles.get(vid)
        d = drivers.get(loc.driver_id) if loc.driver_id else None
        rows.append(
            {
                **serialize_location(loc),
                "plate_number": v.plate_number if v else None,
                "model": v.model if v else None,
                "vehicle_status": v.status if v else None,
                "driver_name": d.full_name if d else None,
                "driver_phone": d.phone if d else None,
            }
        )
    return {"locations": rows}


@router.get("/live")
def gps_live_alias(
    vehicle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Alias for GET /gps/location/latest."""
    return latest_locations(vehicle_id=vehicle_id, db=db, user=user)


@router.get("/location/history")
def location_history(
    vehicle_id: int = Query(...),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_read_fleet(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = (
        db.query(GpsLocation)
        .filter(GpsLocation.vehicle_id == vehicle_id)
        .order_by(desc(GpsLocation.recorded_at))
        .limit(limit)
        .all()
    )
    return {
        "vehicle_id": vehicle_id,
        "history": [
            {
                "latitude": r.latitude,
                "longitude": r.longitude,
                "speed": r.speed,
                "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
            }
            for r in reversed(rows)
        ],
    }


@router.get("/history/{vehicle_id}")
def gps_history_alias(
    vehicle_id: int,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Alias for GET /gps/location/history?vehicle_id=…"""
    return location_history(vehicle_id=vehicle_id, limit=limit, db=db, user=user)


@router.get("/tasks")
def list_transport_tasks(
    status: str = Query(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_read_fleet(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    query = db.query(TransportTask).options(
        joinedload(TransportTask.vehicle), joinedload(TransportTask.driver)
    )
    if status:
        query = query.filter(TransportTask.status == status)
    tasks = query.order_by(desc(TransportTask.created_at)).limit(200).all()
    latest = latest_locations_by_vehicle(db)
    return {
        "tasks": [
            _serialize_transport_task(t, latest.get(t.vehicle_id) if t.vehicle_id else None)
            for t in tasks
        ]
    }


@router.post("/tasks")
def create_transport_task(
    payload: TransportTaskIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_manage(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title required")
    if payload.vehicle_id is not None:
        if not db.query(Vehicle).filter(Vehicle.id == payload.vehicle_id).first():
            raise HTTPException(status_code=404, detail="Vehicle not found")
    if payload.driver_id is not None:
        if not db.query(Driver).filter(Driver.id == payload.driver_id).first():
            raise HTTPException(status_code=404, detail="Driver not found")
    task = TransportTask(
        title=title,
        description=payload.description.strip(),
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
        transport_id=payload.transport_id,
        origin=payload.origin.strip(),
        destination=payload.destination.strip(),
        status=payload.status,
        created_by=user.username,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    task = (
        db.query(TransportTask)
        .options(joinedload(TransportTask.vehicle), joinedload(TransportTask.driver))
        .filter(TransportTask.id == task.id)
        .first()
    )
    log_action(db, user.username, "transport_task_create", f"task={task.id}")
    return _serialize_transport_task(task, None)


@router.put("/tasks/{task_id}")
def update_transport_task(
    task_id: int,
    payload: TransportTaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_manage(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    task = (
        db.query(TransportTask)
        .options(joinedload(TransportTask.vehicle), joinedload(TransportTask.driver))
        .filter(TransportTask.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key in ("origin", "destination", "description") and value is not None:
            value = value.strip()
        if key == "title" and value is not None:
            value = value.strip()
            if not value:
                raise HTTPException(status_code=400, detail="title required")
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    loc = latest_locations_by_vehicle(db).get(task.vehicle_id) if task.vehicle_id else None
    return _serialize_transport_task(task, loc)


@router.post("/tasks/{task_id}/start")
def start_transport_task_tracking(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = db.query(TransportTask).filter(TransportTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not task.vehicle_id:
        raise HTTPException(status_code=400, detail="Assign a vehicle first")
    task.tracking_active = True
    task.status = "active"
    task.started_at = task.started_at or datetime.utcnow()
    if task.driver_id:
        driver = db.query(Driver).filter(Driver.id == task.driver_id).first()
        if driver:
            driver.status = "on_trip"
    db.commit()
    log_action(db, user.username, "transport_task_start", f"task={task_id}")
    task = (
        db.query(TransportTask)
        .options(joinedload(TransportTask.vehicle), joinedload(TransportTask.driver))
        .filter(TransportTask.id == task_id)
        .first()
    )
    loc = latest_locations_by_vehicle(db).get(task.vehicle_id)
    return _serialize_transport_task(task, loc)


@router.post("/tasks/{task_id}/stop")
def stop_transport_task_tracking(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = db.query(TransportTask).filter(TransportTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.tracking_active = False
    task.status = "completed"
    task.completed_at = datetime.utcnow()
    if task.driver_id:
        driver = db.query(Driver).filter(Driver.id == task.driver_id).first()
        if driver and driver.status == "on_trip":
            driver.status = "active"
    db.commit()
    log_action(db, user.username, "transport_task_stop", f"task={task_id}")
    task = (
        db.query(TransportTask)
        .options(joinedload(TransportTask.vehicle), joinedload(TransportTask.driver))
        .filter(TransportTask.id == task_id)
        .first()
    )
    loc = latest_locations_by_vehicle(db).get(task.vehicle_id) if task.vehicle_id else None
    return _serialize_transport_task(task, loc)


@router.get("/trips")
def list_trips(
    status: str = Query(default=""),
    transport_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_view(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    query = db.query(TripRoute).options(
        joinedload(TripRoute.vehicle), joinedload(TripRoute.driver)
    )
    if status:
        query = query.filter(TripRoute.status == status)
    if transport_id is not None:
        query = query.filter(TripRoute.transport_id == transport_id)
    trips = query.order_by(desc(TripRoute.created_at)).limit(200).all()
    return {"trips": [_serialize_trip(t) for t in trips]}


@router.post("/trips")
def create_trip(
    payload: TripIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_manage(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    vehicle = db.query(Vehicle).filter(Vehicle.id == payload.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if payload.driver_id is not None:
        driver = db.query(Driver).filter(Driver.id == payload.driver_id).first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
    if payload.transport_id is not None:
        transport = db.query(Transport).filter(Transport.id == payload.transport_id).first()
        if not transport:
            raise HTTPException(status_code=404, detail="Transport not found")

    trip = TripRoute(
        transport_id=payload.transport_id,
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
        origin=payload.origin.strip(),
        destination=payload.destination.strip(),
        status=payload.status,
        started_at=datetime.utcnow() if payload.status in ("Active", "In Transit") else None,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    trip = (
        db.query(TripRoute)
        .options(joinedload(TripRoute.vehicle), joinedload(TripRoute.driver))
        .filter(TripRoute.id == trip.id)
        .first()
    )
    log_action(db, user.username, "gps_trip_create", f"trip={trip.id}")
    return _serialize_trip(trip)


@router.get("/dashboard")
def gps_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_view(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    return build_dashboard(db)
