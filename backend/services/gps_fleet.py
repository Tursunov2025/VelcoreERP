"""Phase 12 — GPS fleet helpers (latest positions, dashboard stats)."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from models import Driver, GpsLocation, TripRoute, Transport, Vehicle

ONLINE_WINDOW_MINUTES = 10
ACTIVE_TRIP_STATUSES = ("Planned", "Active", "In Transit")


def latest_location_for_vehicle(db: Session, vehicle_id: int) -> GpsLocation | None:
    return (
        db.query(GpsLocation)
        .filter(GpsLocation.vehicle_id == vehicle_id)
        .order_by(desc(GpsLocation.recorded_at), desc(GpsLocation.id))
        .first()
    )


def serialize_location(loc: GpsLocation | None) -> dict | None:
    if not loc:
        return None
    now = datetime.utcnow()
    age_sec = (now - (loc.recorded_at or now)).total_seconds() if loc.recorded_at else 9999
    return {
        "id": loc.id,
        "vehicle_id": loc.vehicle_id,
        "driver_id": loc.driver_id,
        "latitude": loc.latitude,
        "longitude": loc.longitude,
        "speed": loc.speed,
        "battery_level": loc.battery_level,
        "recorded_at": loc.recorded_at.isoformat() if loc.recorded_at else None,
        "online": age_sec <= ONLINE_WINDOW_MINUTES * 60,
        "seconds_since_update": int(age_sec),
    }


def latest_locations_by_vehicle(db: Session) -> dict[int, GpsLocation]:
    """Most recent GPS row per vehicle."""
    rows = (
        db.query(GpsLocation)
        .order_by(GpsLocation.vehicle_id, desc(GpsLocation.recorded_at), desc(GpsLocation.id))
        .all()
    )
    out: dict[int, GpsLocation] = {}
    for row in rows:
        if row.vehicle_id not in out:
            out[row.vehicle_id] = row
    return out


def gps_for_transport(db: Session, transport_id: int) -> dict | None:
    trip = (
        db.query(TripRoute)
        .filter(TripRoute.transport_id == transport_id)
        .order_by(desc(TripRoute.started_at), desc(TripRoute.id))
        .first()
    )
    if not trip:
        return None
    loc = latest_location_for_vehicle(db, trip.vehicle_id)
    vehicle = db.query(Vehicle).filter(Vehicle.id == trip.vehicle_id).first()
    driver = (
        db.query(Driver).filter(Driver.id == trip.driver_id).first()
        if trip.driver_id
        else None
    )
    history = (
        db.query(GpsLocation)
        .filter(GpsLocation.vehicle_id == trip.vehicle_id)
        .order_by(desc(GpsLocation.recorded_at))
        .limit(50)
        .all()
    )
    return {
        "trip_id": trip.id,
        "trip_status": trip.status,
        "origin": trip.origin,
        "destination": trip.destination,
        "vehicle": {
            "id": vehicle.id,
            "plate_number": vehicle.plate_number,
            "model": vehicle.model,
        }
        if vehicle
        else None,
        "driver": {
            "id": driver.id,
            "full_name": driver.full_name,
            "phone": driver.phone,
        }
        if driver
        else None,
        "latest": serialize_location(loc),
        "route_history": [
            {
                "latitude": h.latitude,
                "longitude": h.longitude,
                "speed": h.speed,
                "recorded_at": h.recorded_at.isoformat() if h.recorded_at else None,
            }
            for h in reversed(history)
        ],
    }


def build_dashboard(db: Session) -> dict:
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=ONLINE_WINDOW_MINUTES)
    latest = latest_locations_by_vehicle(db)

    online_trucks = sum(
        1 for loc in latest.values() if loc.recorded_at and loc.recorded_at >= cutoff
    )
    active_routes = (
        db.query(TripRoute)
        .filter(TripRoute.status.in_(ACTIVE_TRIP_STATUSES))
        .count()
    )

    recent_speeds = (
        db.query(GpsLocation.speed)
        .filter(GpsLocation.recorded_at >= now - timedelta(hours=24))
        .filter(GpsLocation.speed > 0)
        .all()
    )
    avg_speed = 0.0
    if recent_speeds:
        avg_speed = round(sum(s[0] for s in recent_speeds) / len(recent_speeds), 1)

    eta_rows = []
    trips = (
        db.query(TripRoute)
        .filter(TripRoute.status.in_(ACTIVE_TRIP_STATUSES))
        .order_by(desc(TripRoute.started_at))
        .limit(10)
        .all()
    )
    for trip in trips:
        transport = (
            db.query(Transport).filter(Transport.id == trip.transport_id).first()
            if trip.transport_id
            else None
        )
        vehicle = db.query(Vehicle).filter(Vehicle.id == trip.vehicle_id).first()
        eta = None
        if transport and transport.arrival_date:
            eta = transport.arrival_date.isoformat()
        elif trip.started_at:
            eta = (trip.started_at + timedelta(hours=48)).isoformat()
        eta_rows.append(
            {
                "trip_id": trip.id,
                "transport_id": trip.transport_id,
                "plate_number": vehicle.plate_number if vehicle else "",
                "destination": trip.destination,
                "status": trip.status,
                "eta": eta,
            }
        )

    return {
        "online_trucks": online_trucks,
        "total_vehicles": db.query(Vehicle).count(),
        "active_routes": active_routes,
        "average_speed_kmh": avg_speed,
        "eta_arrivals": eta_rows,
    }
