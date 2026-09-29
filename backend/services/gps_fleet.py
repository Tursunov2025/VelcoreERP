"""Phase 12 — GPS fleet helpers (latest positions, dashboard stats, live tracking)."""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from models import Driver, GpsLocation, TripRoute, Transport, Vehicle, MesGpsDevice
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
STATIONARY_HEARTBEAT_SAVE_SECONDS = 30


def _device_location_proxy(device):
    if not device or device.last_latitude is None or device.last_longitude is None:
        return None
    return SimpleNamespace(
        id=f"device-{device.id}",
        vehicle_id=device.vehicle_id,
        driver_id=device.driver_user_id,
        latitude=device.last_latitude,
        longitude=device.last_longitude,
        speed=device.last_speed_kmh,
        battery_level=None,
        recorded_at=device.last_seen_at,
    )


def latest_location_for_vehicle(db: Session, vehicle_id: int):
    legacy = (
        db.query(GpsLocation)
        .filter(GpsLocation.vehicle_id == vehicle_id)
        .order_by(desc(GpsLocation.recorded_at), desc(GpsLocation.id))
        .first()
    )

    device = (
        db.query(MesGpsDevice)
        .filter(
            MesGpsDevice.vehicle_id == vehicle_id,
            MesGpsDevice.status == "active",
            MesGpsDevice.last_latitude.isnot(None),
            MesGpsDevice.last_longitude.isnot(None),
        )
        .order_by(desc(MesGpsDevice.last_seen_at), desc(MesGpsDevice.id))
        .first()
    )
    physical = _device_location_proxy(device)

    if not legacy:
        return physical
    if not physical:
        return legacy

    legacy_time = legacy.recorded_at or datetime.min
    physical_time = physical.recorded_at or datetime.min
    return physical if physical_time >= legacy_time else legacy


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


def latest_locations_by_vehicle(db: Session) -> dict[int, object]:
    """Latest location per vehicle, including physical GPS devices without a trip."""
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

    latest = {row.vehicle_id: row for row in rows}

    devices = (
        db.query(MesGpsDevice)
        .filter(
            MesGpsDevice.status == "active",
            MesGpsDevice.last_latitude.isnot(None),
            MesGpsDevice.last_longitude.isnot(None),
        )
        .all()
    )

    for device in devices:
        physical = _device_location_proxy(device)
        if not physical:
            continue

        current = latest.get(device.vehicle_id)
        if current is None:
            latest[device.vehicle_id] = physical
            continue

        current_time = current.recorded_at or datetime.min
        physical_time = physical.recorded_at or datetime.min
        if physical_time >= current_time:
            latest[device.vehicle_id] = physical

    return latest


def should_save_location(
    prev: GpsLocation | None,
    latitude: float,
    longitude: float,
    recorded_at: datetime,
) -> bool:
    """Keep movement points and periodic stationary heartbeat points."""
    if not prev:
        return True

    dist = haversine_meters(
        prev.latitude,
        prev.longitude,
        latitude,
        longitude,
    )

    if prev.recorded_at:
        elapsed = (recorded_at - prev.recorded_at).total_seconds()

        # Ignore invalid/out-of-order timestamps.
        if elapsed <= 0:
            return False

        # Protect the GPS database from impossible coordinate jumps.
        # A long gap can happen when the tracker is offline, so do not
        # reject a point solely because the elapsed time is large.
        if elapsed <= 300:
            implied_speed_kmh = (dist / elapsed) * 3.6
            if implied_speed_kmh > 160.0:
                return False

        if elapsed >= STATIONARY_HEARTBEAT_SAVE_SECONDS and dist < DEDUP_DISTANCE_METERS:
            return True

    if dist >= DEDUP_DISTANCE_METERS:
        return True

    return False


def save_location(
    db: Session,
    *,
    vehicle_id: int,
    driver_id: int | None,
    latitude: float,
    longitude: float,
    speed: float,
    battery_level: float | None,
    recorded_at: datetime | None = None,
) -> tuple[GpsLocation, bool]:
    """
    Insert GPS row unless duplicate within 5 m of last point.
    Returns (location, saved_new_row).
    """
    prev = (
        db.query(GpsLocation)
        .filter(GpsLocation.vehicle_id == vehicle_id)
        .order_by(desc(GpsLocation.recorded_at), desc(GpsLocation.id))
        .first()
    )
    effective_recorded_at = recorded_at or datetime.utcnow()

    if getattr(effective_recorded_at, "tzinfo", None) is not None:
        effective_recorded_at = effective_recorded_at.replace(tzinfo=None)

    if not should_save_location(
        prev,
        latitude,
        longitude,
        effective_recorded_at,
    ):
        return prev, False

    loc = GpsLocation(
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        latitude=latitude,
        longitude=longitude,
        speed=speed,
        battery_level=battery_level,
        recorded_at=effective_recorded_at,
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
