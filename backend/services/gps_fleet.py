"""Phase 12 — GPS fleet helpers (latest positions, dashboard stats, live tracking)."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from models import Driver, GpsLocation, TripRoute, Transport, Vehicle
from services.gps_geocode import (
    coords_for_destination,
    estimate_eta_hours,
    haversine_meters,
    reverse_geocode,
)

# Live map "online" if updated within this window (5s upload cadence)
LIVE_ONLINE_THRESHOLD_SEC = 20
OFFLINE_ALERT_MINUTES = 10
ACTIVE_TRIP_STATUSES = ("Planned", "Active", "In Transit")
MOVING_SPEED_KMH = 5.0
DEDUP_DISTANCE_METERS = 5.0


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
    moving = (loc.speed or 0) > MOVING_SPEED_KMH
    return {
        "id": loc.id,
        "vehicle_id": loc.vehicle_id,
        "driver_id": loc.driver_id,
        "latitude": loc.latitude,
        "longitude": loc.longitude,
        "speed": loc.speed,
        "battery_level": loc.battery_level,
        "recorded_at": loc.recorded_at.isoformat() if loc.recorded_at else None,
        "online": age_sec <= LIVE_ONLINE_THRESHOLD_SEC,
        "moving": moving and age_sec <= LIVE_ONLINE_THRESHOLD_SEC,
        "seconds_since_update": int(age_sec),
    }


def latest_locations_by_vehicle(db: Session) -> dict[int, GpsLocation]:
    """Most recent GPS row per vehicle (SQL max id per group)."""
    subq = (
        db.query(
            GpsLocation.vehicle_id.label("vehicle_id"),
            func.max(GpsLocation.id).label("max_id"),
        )
        .group_by(GpsLocation.vehicle_id)
        .subquery()
    )
    rows = (
        db.query(GpsLocation)
        .join(
            subq,
            (GpsLocation.vehicle_id == subq.c.vehicle_id)
            & (GpsLocation.id == subq.c.max_id),
        )
        .all()
    )
    return {row.vehicle_id: row for row in rows}


def should_save_location(
    prev: GpsLocation | None,
    latitude: float,
    longitude: float,
) -> bool:
    """Skip insert when coords unchanged within DEDUP_DISTANCE_METERS."""
    if not prev:
        return True
    dist = haversine_meters(prev.latitude, prev.longitude, latitude, longitude)
    return dist >= DEDUP_DISTANCE_METERS


def save_location(
    db: Session,
    *,
    vehicle_id: int,
    driver_id: int | None,
    latitude: float,
    longitude: float,
    speed: float,
    battery_level: float | None,
) -> tuple[GpsLocation, bool]:
    """
    Insert GPS row unless duplicate within 5 m of last point.
    Returns (location, saved_new_row).
    """
    prev = latest_location_for_vehicle(db, vehicle_id)
    if not should_save_location(prev, latitude, longitude):
        return prev, False

    loc = GpsLocation(
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        latitude=latitude,
        longitude=longitude,
        speed=speed,
        battery_level=battery_level,
        recorded_at=datetime.utcnow(),
    )
    db.add(loc)
    db.flush()
    return loc, True


def _vehicle_motion_bucket(loc: GpsLocation | None, cutoff: datetime) -> str:
    if not loc or not loc.recorded_at or loc.recorded_at < cutoff:
        return "offline"
    if (loc.speed or 0) > MOVING_SPEED_KMH:
        return "moving"
    return "stopped"


def build_dashboard(db: Session) -> dict:
    now = datetime.utcnow()
    live_cutoff = now - timedelta(seconds=LIVE_ONLINE_THRESHOLD_SEC)
    latest = latest_locations_by_vehicle(db)

    online_trucks = 0
    moving_vehicles = 0
    stopped_vehicles = 0
    for loc in latest.values():
        bucket = _vehicle_motion_bucket(loc, live_cutoff)
        if bucket == "offline":
            continue
        online_trucks += 1
        if bucket == "moving":
            moving_vehicles += 1
        else:
            stopped_vehicles += 1

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
    vehicles_by_id = {v.id: v for v in db.query(Vehicle).all()}
    drivers_by_id = {d.id: d for d in db.query(Driver).all()}
    live_vehicles = []
    for vid, loc in sorted(latest.items(), key=lambda x: x[0]):
        v = vehicles_by_id.get(vid)
        d = drivers_by_id.get(loc.driver_id) if loc.driver_id else None
        ser = serialize_location(loc) or {}
        live_vehicles.append(
            {
                **ser,
                "plate_number": v.plate_number if v else None,
                "model": v.model if v else None,
                "driver_name": d.full_name if d else None,
            }
        )

    for trip in trips:
        transport = (
            db.query(Transport).filter(Transport.id == trip.transport_id).first()
            if trip.transport_id
            else None
        )
        vehicle = db.query(Vehicle).filter(Vehicle.id == trip.vehicle_id).first()
        loc = latest.get(trip.vehicle_id)
        dest_coords = coords_for_destination(trip.destination or "")
        eta_hours = None
        current_city = ""
        if loc:
            if dest_coords:
                eta_hours = estimate_eta_hours(
                    loc.latitude,
                    loc.longitude,
                    dest_coords[0],
                    dest_coords[1],
                    loc.speed or 0,
                )
            geo = reverse_geocode(loc.latitude, loc.longitude)
            current_city = geo.get("city") or ""

        eta = None
        if eta_hours is not None:
            eta = (now + timedelta(hours=eta_hours)).isoformat()
        elif transport and transport.arrival_date:
            eta = transport.arrival_date.isoformat()
        elif trip.started_at:
            eta = (trip.started_at + timedelta(hours=48)).isoformat()

        eta_rows.append(
            {
                "trip_id": trip.id,
                "transport_id": trip.transport_id,
                "plate_number": vehicle.plate_number if vehicle else "",
                "destination": trip.destination,
                "current_city": current_city,
                "status": trip.status,
                "eta": eta,
                "eta_hours": eta_hours,
            }
        )

    return {
        "online_trucks": online_trucks,
        "moving_vehicles": moving_vehicles,
        "stopped_vehicles": stopped_vehicles,
        "total_vehicles": db.query(Vehicle).count(),
        "active_routes": active_routes,
        "average_speed_kmh": avg_speed,
        "eta_arrivals": eta_rows,
        "live_vehicles": live_vehicles,
        "refresh_interval_sec": 5,
    }


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

    current_city = ""
    eta_hours = None
    dest_coords = coords_for_destination(trip.destination or "")
    if loc:
        geo = reverse_geocode(loc.latitude, loc.longitude)
        current_city = geo.get("city") or geo.get("country") or ""
        if dest_coords:
            eta_hours = estimate_eta_hours(
                loc.latitude,
                loc.longitude,
                dest_coords[0],
                dest_coords[1],
                loc.speed or 0,
            )

    latest = serialize_location(loc)
    if latest:
        latest["current_city"] = current_city
        latest["eta_hours"] = eta_hours

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
        "latest": latest,
        "current_city": current_city,
        "eta_hours": eta_hours,
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
