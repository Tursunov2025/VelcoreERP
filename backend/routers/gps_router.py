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
from models import Driver, GpsLocation, TripRoute, Transport, User, Vehicle
from services.audit import log_action
from services.gps_fleet import (
    build_dashboard,
    latest_locations_by_vehicle,
    serialize_location,
)
from services.permissions import user_has_permission

router = APIRouter(prefix="/gps", tags=["gps"])

TRIP_STATUSES = ["Planned", "Active", "In Transit", "Completed", "Cancelled"]
VEHICLE_STATUSES = ["active", "inactive", "maintenance"]
DRIVER_STATUSES = ["active", "inactive", "on_trip"]


def _can_view(db: Session, user: User) -> bool:
    return user.role == "admin" or user_has_permission(db, user, "export_view")


def _can_manage(db: Session, user: User) -> bool:
    return user.role == "admin" or user_has_permission(db, user, "export_manage")


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


@router.get("/vehicles")
def list_vehicles(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_view(db, user):
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
    if not _can_view(db, user):
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


@router.post("/location/update")
def update_location(
    payload: LocationUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    vehicle = db.query(Vehicle).filter(Vehicle.id == payload.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if payload.driver_id is not None:
        driver = db.query(Driver).filter(Driver.id == payload.driver_id).first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        driver.status = "on_trip"
    loc = GpsLocation(
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed=payload.speed,
        battery_level=payload.battery_level,
        recorded_at=datetime.utcnow(),
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    log_action(
        db,
        user.username,
        "gps_location_update",
        f"vehicle={payload.vehicle_id} lat={payload.latitude}",
    )
    return serialize_location(loc)


@router.get("/location/latest")
def latest_locations(
    vehicle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_view(db, user):
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


@router.get("/location/history")
def location_history(
    vehicle_id: int = Query(...),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_view(db, user):
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
