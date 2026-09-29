"""IDOR-safe GPS API for canonical finished-logistics trips."""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import (GpsAlertState, GpsLocation, GpsVehicleStop, MesGpsDevice, MesTrip,
                    MesTripLatestLocation, MesTripLocation, MesTripTrackingSession,
                    MesVehicle, ProductionProject, User, UserIdentityProfile)
from services.gps_geocode import haversine_meters, reverse_geocode
from services.platform_administration import get_versioned_setting, put_versioned_setting
from services.permissions import user_has_permission
from services.trip_tracking import (
    GPS_POLICY_DEFAULTS, TripTrackingError, append_locations, effective_health, gps_policy,
    heartbeat, require_assigned_trip, revoke_session, serialize_location,
    serialize_session, start_session, stop_session, validate_policy,
)

router = APIRouter(prefix="/mes/finished-logistics", tags=["mes-trip-tracking"])


class SessionStart(BaseModel):
    client_session_id: str = Field(..., min_length=8, max_length=180)
    device_identifier: str | None = Field(default=None, min_length=1, max_length=180)


class LocationPoint(BaseModel):
    client_point_id: str = Field(..., min_length=8, max_length=180)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_m: float | None = Field(None, ge=0, le=10000)
    speed_kmh: float | None = Field(None, ge=0, le=500)
    heading_deg: float | None = Field(None, ge=0, lt=360)
    battery_level: float | None = Field(None, ge=0, le=100)
    captured_at: datetime
    was_queued: bool = False


class LocationBatch(BaseModel):
    points: list[LocationPoint] = Field(..., min_length=1, max_length=250)

class Heartbeat(BaseModel):
    state: str
    queued_point_count: int = Field(0, ge=0, le=100000)
    accuracy_m: float | None = Field(None, ge=0, le=10000)
    battery_level: float | None = Field(None, ge=0, le=100)

class GpsPolicyUpdate(BaseModel):
    version: int = Field(..., ge=1)
    moving_interval_seconds: int
    stationary_interval_seconds: int
    significant_displacement_meters: int
    offline_retention_hours: int
    maximum_batch_size: int
    stale_threshold_seconds: int
    route_deviation_meters: int
    long_stop_seconds: int
    history_retention_days: int


def _error(exc: TripTrackingError):
    raise HTTPException(exc.status_code, detail={"code": exc.code}) from exc


def _track(db: Session, user: User):
    if not user_has_permission(db, user, "gps_trip_track"):
        raise HTTPException(403, detail={"code": "permission_denied"})


def _view(db: Session, user: User):
    if not user_has_permission(db, user, "gps_trip_view") and not user_has_permission(db, user, "mes_terminal_dispatch"):
        raise HTTPException(403, detail={"code": "permission_denied"})


@router.get("/driver/trips/active")
def active_driver_trips(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _track(db, user)
    rows = db.query(MesTrip).filter(
        MesTrip.driver_user_id == user.id,
        MesTrip.status.in_(["loading", "loaded", "dispatched", "in_transit", "arrived", "delivered"]),
    ).order_by(MesTrip.planned_departure_at, MesTrip.id).all()
    return {"trips": [{
        "id": row.id, "trip_number": row.trip_number, "status": row.status,
        "vehicle_id": row.vehicle_id, "destination_city": row.destination_city,
        "destination_site": row.destination_site, "destination_address": row.destination_address,
        "planned_departure_at": row.planned_departure_at, "delivery_deadline_at": row.delivery_deadline_at,
        "actual_departure_at": row.actual_departure_at, "arrived_at": row.arrived_at, "version": row.version,
    } for row in rows]}


@router.post("/trips/{trip_id}/tracking/start")
def tracking_start(trip_id: int, data: SessionStart, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _track(db, user)
    try:
        row, authorization = start_session(db, trip_id, user, data.client_session_id, data.device_identifier); db.commit()
        return {**serialize_session(row), "tracking_authorization": authorization}
    except TripTrackingError as exc:
        db.rollback(); _error(exc)


@router.post("/tracking/sessions/{session_id}/locations")
def locations_append(session_id: int, data: LocationBatch, request: Request,
                     x_tracking_authorization: str = Header(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _track(db, user)
    if int(request.headers.get("content-length") or 0) > 512_000:
        raise HTTPException(413, detail={"code": "tracking_request_too_large"})
    try:
        result = append_locations(db, session_id, user, x_tracking_authorization, [point.model_dump() for point in data.points]); db.commit(); return result
    except TripTrackingError as exc:
        db.rollback(); _error(exc)


@router.post("/tracking/sessions/{session_id}/stop")
def tracking_stop(session_id: int, x_tracking_authorization: str = Header(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _track(db, user)
    try:
        row = stop_session(db, session_id, user, x_tracking_authorization); db.commit(); return serialize_session(row)
    except TripTrackingError as exc:
        db.rollback(); _error(exc)


@router.get("/trips/{trip_id}/tracking")
def tracking_read(trip_id: int, limit: int = Query(200, ge=1, le=500), offset: int = Query(0, ge=0, le=100000), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    can_view_all = user_has_permission(db, user, "gps_trip_view") or user_has_permission(db, user, "mes_terminal_dispatch")
    if not can_view_all:
        _track(db, user)
        try:
            require_assigned_trip(db, trip_id, user)
        except TripTrackingError as exc:
            _error(exc)
    trip = db.query(MesTrip).filter_by(id=trip_id).first()
    if not trip:
        raise HTTPException(404, detail={"code": "trip_not_found"})
    rows = db.query(MesTripLocation).filter_by(trip_id=trip.id).order_by(
        MesTripLocation.captured_at.desc(), MesTripLocation.id.desc()
    ).offset(offset).limit(limit).all()
    latest = db.get(MesTripLatestLocation, trip.id)
    total = db.query(MesTripLocation).filter_by(trip_id=trip.id).count()
    return {"trip_id": trip.id, "latest": serialize_location(latest), "history": [serialize_location(row) for row in reversed(rows)], "total": total, "limit": limit, "offset": offset}

@router.post("/tracking/sessions/{session_id}/heartbeat")
def tracking_heartbeat(session_id: int, data: Heartbeat, x_tracking_authorization: str = Header(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _track(db,user)
    try:
        row=heartbeat(db,session_id,user,x_tracking_authorization,data.state,data.queued_point_count,data.accuracy_m,data.battery_level);db.commit();return serialize_session(row)
    except TripTrackingError as exc: db.rollback();_error(exc)

@router.post("/tracking/sessions/{session_id}/revoke")
def tracking_revoke(session_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _view(db,user)
    try: row=revoke_session(db,session_id,user);db.commit();return serialize_session(row)
    except TripTrackingError as exc:db.rollback();_error(exc)

@router.get("/tracking/fleet")
def tracking_fleet(driver_user_id:int|None=None,vehicle_id:int|None=None,trip_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _view(db,user); policy=gps_policy(db); now=datetime.utcnow(); moving_speed_kmh=1.0
    vehicle_query=db.query(MesVehicle).filter(MesVehicle.is_active.is_(True))
    if vehicle_id:vehicle_query=vehicle_query.filter(MesVehicle.id==vehicle_id)
    vehicles=vehicle_query.order_by(MesVehicle.registration_number).all()
    vehicle_ids=[row.id for row in vehicles]
    if not vehicle_ids:return {"items":[],"stale_threshold_seconds":policy["stale_threshold_seconds"],"moving_speed_threshold_kmh":moving_speed_kmh,"generated_at":now}

    device_rows=db.query(MesGpsDevice).filter(MesGpsDevice.vehicle_id.in_(vehicle_ids)).order_by(MesGpsDevice.id.desc()).all()
    devices={}
    for row in device_rows:devices.setdefault(row.vehicle_id,row)
    trip_query=db.query(MesTrip).filter(MesTrip.vehicle_id.in_(vehicle_ids))
    if trip_id:trip_query=trip_query.filter(MesTrip.id==trip_id)
    trips=trip_query.order_by(MesTrip.id.desc()).all()
    active_statuses={"planned","loading","loaded","dispatched","in_transit","arrived"}
    active_trips={}
    for row in trips:
        if row.status in active_statuses:active_trips.setdefault(row.vehicle_id,row)
    latest_rows=db.query(MesTripLatestLocation).filter(MesTripLatestLocation.vehicle_id.in_(vehicle_ids)).order_by(MesTripLatestLocation.received_at.desc()).all()
    latest_by_vehicle={}
    for row in latest_rows:latest_by_vehicle.setdefault(row.vehicle_id,row)
    trip_by_id={row.id:row for row in trips}
    selected_trips={vehicle.id:(active_trips.get(vehicle.id) or trip_by_id.get(getattr(latest_by_vehicle.get(vehicle.id),"trip_id",None))) for vehicle in vehicles}
    selected_trip_ids=[row.id for row in selected_trips.values() if row]
    session_rows=(db.query(MesTripTrackingSession).filter(MesTripTrackingSession.trip_id.in_(selected_trip_ids)).order_by(MesTripTrackingSession.id.desc()).all() if selected_trip_ids else [])
    sessions={}
    for row in session_rows:sessions.setdefault(row.trip_id,row)
    driver_ids={row.driver_user_id for row in selected_trips.values() if row and row.driver_user_id}
    driver_ids.update(row.driver_user_id for row in devices.values() if row.driver_user_id)
    profiles={row.user_id:row for row in db.query(UserIdentityProfile).filter(UserIdentityProfile.user_id.in_(driver_ids)).all()} if driver_ids else {}
    users={row.id:row for row in db.query(User).filter(User.id.in_(driver_ids)).all()} if driver_ids else {}
    project_ids={row.project_id for row in selected_trips.values() if row}
    projects={row.id:row for row in db.query(ProductionProject).filter(ProductionProject.id.in_(project_ids)).all()} if project_ids else {}

    alert_state_rows = (
        db.query(GpsAlertState)
        .filter(GpsAlertState.vehicle_id.in_(vehicle_ids))
        .all()
    )
    alert_states = {}
    for row in alert_state_rows:
        alert_states.setdefault(row.vehicle_id, row)

    # Today's travelled distance in Uzbekistan local time.
    local_tz = ZoneInfo("Asia/Tashkent")
    local_now = datetime.now(local_tz)
    local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = local_start.astimezone(timezone.utc).replace(tzinfo=None)
    now_utc = local_now.astimezone(timezone.utc).replace(tzinfo=None)

    # Current week: Monday 00:00 Asia/Tashkent -> now.
    week_start_local = local_start - timedelta(days=local_start.weekday())
    week_start_utc = week_start_local.astimezone(timezone.utc).replace(tzinfo=None)

    # Load GPS once from the current week onward.
    # Daily and weekly distances are calculated from this single query.
    weekly_rows = (
        db.query(
            GpsLocation.vehicle_id,
            GpsLocation.latitude,
            GpsLocation.longitude,
            GpsLocation.speed,
            GpsLocation.recorded_at,
        )
        .filter(
            GpsLocation.vehicle_id.in_(vehicle_ids),
            GpsLocation.recorded_at >= week_start_utc,
            GpsLocation.recorded_at <= now_utc,
        )
        .order_by(GpsLocation.vehicle_id, GpsLocation.recorded_at, GpsLocation.id)
        .all()
    )

    def _distance_by_vehicle(rows):
        grouped = {}
        for row in rows:
            grouped.setdefault(row.vehicle_id, []).append(row)

        result = {}
        for vid, points in grouped.items():
            meters = 0.0

            for prev, cur in zip(points, points[1:]):
                if (
                    prev.latitude is None
                    or prev.longitude is None
                    or cur.latitude is None
                    or cur.longitude is None
                    or prev.recorded_at is None
                    or cur.recorded_at is None
                ):
                    continue

                dt_seconds = (cur.recorded_at - prev.recorded_at).total_seconds()
                if dt_seconds <= 0:
                    continue

                if dt_seconds > 300.0:
                    continue

                segment_m = haversine_meters(
                    prev.latitude,
                    prev.longitude,
                    cur.latitude,
                    cur.longitude,
                )

                if segment_m < 12.0:
                    continue

                prev_speed = float(prev.speed or 0.0)
                cur_speed = float(cur.speed or 0.0)

                if prev_speed <= 1.5 and cur_speed <= 1.5 and segment_m < 50.0:
                    continue

                implied_speed_kmh = (segment_m / dt_seconds) * 3.6
                if implied_speed_kmh > 160.0:
                    continue

                meters += segment_m

            result[vid] = round(meters / 1000.0, 2)

        return result

    # Weekly distance.
    weekly_distance_km = _distance_by_vehicle(weekly_rows)

    # Daily distance from the same weekly query.
    daily_rows = [
        row for row in weekly_rows
        if row.recorded_at >= start_utc
    ]
    daily_distance_km = _distance_by_vehicle(daily_rows)

    # Total distance currently remains a separate query because it may
    # contain retained GPS older than the current week.
    total_rows = (
        db.query(
            GpsLocation.vehicle_id,
            GpsLocation.latitude,
            GpsLocation.longitude,
            GpsLocation.speed,
            GpsLocation.recorded_at,
        )
        .filter(GpsLocation.vehicle_id.in_(vehicle_ids))
        .order_by(GpsLocation.vehicle_id, GpsLocation.recorded_at, GpsLocation.id)
        .all()
    )
    total_distance_km = _distance_by_vehicle(total_rows)
    out=[]
    for vehicle in vehicles:
        trip=selected_trips.get(vehicle.id); latest=latest_by_vehicle.get(vehicle.id); device=devices.get(vehicle.id)
        session=sessions.get(trip.id) if trip else None
        driver_id=(trip.driver_user_id if trip else None) or (device.driver_user_id if device else None)
        profile=profiles.get(driver_id); driver=users.get(driver_id); project=projects.get(trip.project_id) if trip else None
        # Device capture time is authoritative for fleet freshness. A buffered
        # point received now must not make an offline tracker appear live.
        physical_latest = None
        if not latest and device and device.last_latitude is not None and device.last_longitude is not None:
            physical_latest = {
                "latitude": device.last_latitude,
                "longitude": device.last_longitude,
                "accuracy_m": None,
                "speed_kmh": device.last_speed_kmh,
                "heading_deg": device.last_heading_deg,
                "battery_level": None,
                "captured_at": device.last_seen_at,
                "received_at": device.last_seen_at,
            }

        signal_at = (
            (latest.captured_at or latest.received_at)
            if latest
            else (device.last_seen_at if physical_latest else None)
        )
        age_seconds=max(0,int((now-signal_at).total_seconds())) if signal_at else None
        current_speed = latest.speed_kmh if latest else (device.last_speed_kmh if physical_latest else None)

        if not device:display_status="unbound"
        elif not latest and not physical_latest:display_status="no_signal"
        elif age_seconds is None or age_seconds>policy["stale_threshold_seconds"]:display_status="stale"
        elif float(current_speed or 0)>moving_speed_kmh:display_status="moving"
        else:display_status="stopped"
        if driver_user_id and driver_id!=driver_user_id:continue

        alert_state = alert_states.get(vehicle.id)

        geofence_distance_m = None
        geofence_status = "disabled"

        current_point = latest or physical_latest
        if (
            alert_state
            and alert_state.geofence_enabled
            and alert_state.geofence_latitude is not None
            and alert_state.geofence_longitude is not None
            and alert_state.geofence_radius_m is not None
            and current_point
        ):
            point_lat = current_point.latitude if hasattr(current_point, "latitude") else current_point.get("latitude")
            point_lon = current_point.longitude if hasattr(current_point, "longitude") else current_point.get("longitude")

            if point_lat is not None and point_lon is not None:
                geofence_distance_m = haversine_meters(
                    float(alert_state.geofence_latitude),
                    float(alert_state.geofence_longitude),
                    float(point_lat),
                    float(point_lon),
                )
                geofence_status = (
                    "outside"
                    if geofence_distance_m > float(alert_state.geofence_radius_m)
                    else "inside"
                )

        out.append({
            "vehicle_id":vehicle.id,"registration_number":vehicle.registration_number,"vehicle_type":vehicle.vehicle_type,
            "daily_distance_km":daily_distance_km.get(vehicle.id, 0.0),
            "weekly_distance_km":weekly_distance_km.get(vehicle.id, 0.0),
            "total_distance_km":total_distance_km.get(vehicle.id, 0.0),
            "geofence_enabled":bool(alert_state.geofence_enabled) if alert_state else False,
            "geofence_radius_m":alert_state.geofence_radius_m if alert_state else None,
            "geofence_latitude":alert_state.geofence_latitude if alert_state else None,
            "geofence_longitude":alert_state.geofence_longitude if alert_state else None,
            "geofence_distance_m":round(geofence_distance_m, 1) if geofence_distance_m is not None else None,
            "geofence_status":geofence_status,
            "geofence_alert_active":bool(alert_state.geofence_outside_alert_sent) if alert_state else False,
            "vehicle_model":vehicle.model,"vehicle_internal_code":vehicle.internal_code,"vehicle_operational_state":vehicle.operational_state,
            "device_id":device.id if device else None,"device_identifier":device.device_identifier if device else None,
            "device_status":device.status if device else None,"device_protocol":device.protocol if device else None,
            "speed_limit_kmh":alert_state.speed_limit_kmh if alert_state else None,
            "driver_user_id":driver_id,"driver_name":((profile.full_name if profile else "") or (trip.driver_name_snapshot if trip else "") or vehicle.driver_name or (driver.username if driver else "")),
            "driver_phone":((profile.phone if profile else "") or (trip.driver_phone_snapshot if trip else "") or vehicle.driver_phone),
            "trip_id":trip.id if trip else None,"trip_number":trip.trip_number if trip else "","trip_status":trip.status if trip else None,
            "origin":None,"destination_city":trip.destination_city if trip else "","destination_site":trip.destination_site if trip else "",
            "destination_address":trip.destination_address if trip else "","destination_latitude":getattr(project,"latitude",None) if project else None,
            "destination_longitude":getattr(project,"longitude",None) if project else None,"actual_departure_at":trip.actual_departure_at if trip else None,
            "delivery_deadline_at":trip.delivery_deadline_at if trip else None,"arrived_at":trip.arrived_at if trip else None,
            "session_id":session.id if session else None,"session_status":session.status if session else None,
            "session_started_at":session.started_at if session else None,"health_status":effective_health(session,policy) if session else "offline",
            "status":display_status,"last_contact_at":session.last_contact_at if session else None,
            "last_signal_at":signal_at,"seconds_since_signal":age_seconds,
            "queued_point_count":session.queued_point_count if session else 0,
            "latest":serialize_location(latest) if latest else physical_latest,
        })
    return {"items":out,"stale_threshold_seconds":policy["stale_threshold_seconds"],"moving_speed_threshold_kmh":moving_speed_kmh,"generated_at":now}


@router.get("/tracking/history")
def tracking_history(
    vehicle_id: int = Query(..., ge=1),
    from_at: datetime = Query(..., alias="from"),
    to_at: datetime = Query(..., alias="to"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _view(db, user)

    vehicle = db.query(MesVehicle).filter(MesVehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(404, detail={"code": "vehicle_not_found"})

    def _utc_naive(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo("Asia/Tashkent"))
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    start_utc = _utc_naive(from_at)
    end_utc = _utc_naive(to_at)

    if end_utc <= start_utc:
        raise HTTPException(422, detail={"code": "invalid_time_range"})

    if (end_utc - start_utc) > timedelta(days=31):
        raise HTTPException(422, detail={"code": "time_range_too_large"})

    rows = (
        db.query(GpsLocation)
        .filter(
            GpsLocation.vehicle_id == vehicle_id,
            GpsLocation.recorded_at >= start_utc,
            GpsLocation.recorded_at <= end_utc,
        )
        .order_by(GpsLocation.recorded_at, GpsLocation.id)
        .all()
    )

    distance_m = 0.0
    moving_seconds = 0.0
    stopped_seconds = 0.0
    unknown_seconds = 0.0
    rejected_small = 0
    rejected_drift = 0
    rejected_jump = 0
    rejected_gap = 0
    route = []
    valid_speeds = []

    if rows:
        route.append(rows[0])

    for prev, cur in zip(rows, rows[1:]):
        if not prev.recorded_at or not cur.recorded_at:
            continue

        dt = (cur.recorded_at - prev.recorded_at).total_seconds()
        if dt <= 0:
            continue

        dist = haversine_meters(
            prev.latitude, prev.longitude,
            cur.latitude, cur.longitude
        )

        ps = float(prev.speed or 0.0)
        cs = float(cur.speed or 0.0)

        if dt > 300.0:
            rejected_gap += 1
            unknown_seconds += dt
            continue

        implied = (dist / dt) * 3.6

        # Keep history filtering consistent with the fleet distance
        # calculation and GPS write-layer protection.
        if implied > 160.0:
            rejected_jump += 1
            continue

        # Time accounting is independent from mileage filtering.
        if ps > 5.0 or cs > 5.0:
            moving_seconds += dt
        else:
            stopped_seconds += dt

        if dist < 12.0:
            rejected_small += 1
            continue

        if ps <= 1.5 and cs <= 1.5 and dist < 50.0:
            rejected_drift += 1
            continue

        distance_m += dist

        if cs > 0:
            valid_speeds.append(cs)

        route.append(cur)

    return {
        "vehicle_id": vehicle_id,
        "registration_number": vehicle.registration_number,
        "from": start_utc.isoformat(),
        "to": end_utc.isoformat(),
        "summary": {
            "distance_km": round(distance_m / 1000.0, 2),
            "moving_seconds": int(moving_seconds),
            "stopped_seconds": int(stopped_seconds),
            "unknown_seconds": int(unknown_seconds),
            "average_speed_kmh": round(
                sum(valid_speeds) / len(valid_speeds), 1
            ) if valid_speeds else 0.0,
            "max_speed_kmh": round(max(valid_speeds), 1)
            if valid_speeds else 0.0,
            "raw_points": len(rows),
            "route_points": len(route),
        },
        "quality": {
            "rejected_small": rejected_small,
            "rejected_drift": rejected_drift,
            "rejected_jump": rejected_jump,
            "rejected_gap": rejected_gap,
        },
        "route": [
            {
                "id": row.id,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "speed_kmh": float(row.speed or 0.0),
                "recorded_at": row.recorded_at.isoformat()
                if row.recorded_at else None,
            }
            for row in route
        ],
    }



@router.get("/tracking/history/daily")
def tracking_history_daily(
    vehicle_id: int = Query(..., ge=1),
    from_date: str = Query(...),
    to_date: str = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Daily professional GPS mileage/history summary."""
    _view(db, user)

    vehicle = db.query(MesVehicle).filter(MesVehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(404, detail={"code": "vehicle_not_found"})

    try:
        start_date = datetime.strptime(from_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(to_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(422, detail={"code": "invalid_date_format"})

    if end_date < start_date:
        raise HTTPException(422, detail={"code": "invalid_date_range"})

    if (end_date - start_date).days > 31:
        raise HTTPException(422, detail={"code": "date_range_too_large"})

    tz = ZoneInfo("Asia/Tashkent")
    result = []

    current_date = start_date

    while current_date <= end_date:
        day_start_local = datetime.combine(
            current_date,
            datetime.min.time(),
            tzinfo=tz,
        )
        day_end_local = day_start_local + timedelta(days=1)

        day_start_utc = (
            day_start_local.astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
        day_end_utc = (
            day_end_local.astimezone(timezone.utc)
            .replace(tzinfo=None)
        )

        rows = (
            db.query(GpsLocation)
            .filter(
                GpsLocation.vehicle_id == vehicle_id,
                GpsLocation.recorded_at >= day_start_utc,
                GpsLocation.recorded_at < day_end_utc,
            )
            .order_by(GpsLocation.recorded_at, GpsLocation.id)
            .all()
        )

        distance_m = 0.0
        moving_seconds = 0.0
        stopped_seconds = 0.0
        unknown_seconds = 0.0
        rejected_small = 0
        rejected_drift = 0
        rejected_jump = 0
        rejected_gap = 0
        route_points = 1 if rows else 0
        valid_speeds = []

        for prev, cur in zip(rows, rows[1:]):
            if not prev.recorded_at or not cur.recorded_at:
                continue

            dt = (cur.recorded_at - prev.recorded_at).total_seconds()
            if dt <= 0:
                continue

            dist = haversine_meters(
                prev.latitude,
                prev.longitude,
                cur.latitude,
                cur.longitude,
            )

            ps = float(prev.speed or 0.0)
            cs = float(cur.speed or 0.0)

            if dt > 300.0:
                rejected_gap += 1
                unknown_seconds += dt
                continue

            implied = (dist / dt) * 3.6

            if implied > 200.0:
                rejected_jump += 1
                continue

            # Time accounting is independent from mileage filtering.
            if ps > 5.0 or cs > 5.0:
                moving_seconds += dt
            else:
                stopped_seconds += dt

            if dist < 12.0:
                rejected_small += 1
                continue

            if ps <= 1.5 and cs <= 1.5 and dist < 50.0:
                rejected_drift += 1
                continue

            distance_m += dist
            route_points += 1

            if cs > 0:
                valid_speeds.append(cs)

        result.append({
            "date": current_date.isoformat(),
            "distance_km": round(distance_m / 1000.0, 2),
            "moving_seconds": int(moving_seconds),
            "stopped_seconds": int(stopped_seconds),
            "unknown_seconds": int(unknown_seconds),
            "average_speed_kmh": round(
                sum(valid_speeds) / len(valid_speeds), 1
            ) if valid_speeds else 0.0,
            "max_speed_kmh": round(max(valid_speeds), 1)
            if valid_speeds else 0.0,
            "raw_points": len(rows),
            "route_points": route_points,
            "quality": {
                "rejected_small": rejected_small,
                "rejected_drift": rejected_drift,
                "rejected_jump": rejected_jump,
                "rejected_gap": rejected_gap,
            },
        })

        current_date += timedelta(days=1)

    return {
        "vehicle_id": vehicle_id,
        "registration_number": vehicle.registration_number,
        "from_date": start_date.isoformat(),
        "to_date": end_date.isoformat(),
        "days": result,
    }



@router.get("/tracking/history/stops")
def tracking_history_stops(
    vehicle_id: int = Query(..., ge=1),
    from_at: datetime = Query(..., alias="from"),
    to_at: datetime = Query(..., alias="to"),
    min_stop_seconds: int = Query(300, ge=300, le=86400),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Persistent 5+ minute vehicle stop history."""

    _view(db, user)

    vehicle = db.query(MesVehicle).filter(
        MesVehicle.id == vehicle_id
    ).first()

    if not vehicle:
        raise HTTPException(
            404,
            detail={"code": "vehicle_not_found"},
        )

    def _utc_naive(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(
                tzinfo=ZoneInfo("Asia/Tashkent")
            )
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    start_utc = _utc_naive(from_at)
    end_utc = _utc_naive(to_at)

    if end_utc <= start_utc:
        raise HTTPException(
            422,
            detail={"code": "invalid_time_range"},
        )

    if end_utc - start_utc > timedelta(days=31):
        raise HTTPException(
            422,
            detail={"code": "time_range_too_large"},
        )

    STOP_SPEED_KMH = 5.0
    STOP_RADIUS_METERS = 80.0
    MAX_POINT_GAP_SECONDS = 300.0

    # Keep a small overlap so a stop which is still developing
    # can be extended instead of creating a second stop record.
    processing_start = start_utc - timedelta(minutes=10)

    rows = (
        db.query(GpsLocation)
        .filter(
            GpsLocation.vehicle_id == vehicle_id,
            GpsLocation.recorded_at >= processing_start,
            GpsLocation.recorded_at <= end_utc,
        )
        .order_by(
            GpsLocation.recorded_at,
            GpsLocation.id,
        )
        .all()
    )

    detected = []
    cluster = []

    def finalize_cluster(points):
        if len(points) < 2:
            return

        started_at = points[0].recorded_at
        ended_at = points[-1].recorded_at

        if not started_at or not ended_at:
            return

        duration = (ended_at - started_at).total_seconds()

        if duration < min_stop_seconds:
            return

        lat = sum(float(x.latitude) for x in points) / len(points)
        lng = sum(float(x.longitude) for x in points) / len(points)

        detected.append({
            "start_at": started_at,
            "end_at": ended_at,
            "duration_seconds": int(duration),
            "latitude": round(lat, 7),
            "longitude": round(lng, 7),
            "point_count": len(points),
        })

    for row in rows:
        if not row.recorded_at:
            continue

        speed = float(row.speed or 0.0)

        if speed > STOP_SPEED_KMH:
            finalize_cluster(cluster)
            cluster = []
            continue

        if not cluster:
            cluster = [row]
            continue

        prev = cluster[-1]

        gap = (
            row.recorded_at - prev.recorded_at
        ).total_seconds()

        if gap <= 0 or gap > MAX_POINT_GAP_SECONDS:
            finalize_cluster(cluster)
            cluster = [row]
            continue

        center_lat = (
            sum(float(x.latitude) for x in cluster)
            / len(cluster)
        )
        center_lng = (
            sum(float(x.longitude) for x in cluster)
            / len(cluster)
        )

        drift_m = haversine_meters(
            center_lat,
            center_lng,
            float(row.latitude),
            float(row.longitude),
        )

        if drift_m <= STOP_RADIUS_METERS:
            cluster.append(row)
        else:
            finalize_cluster(cluster)
            cluster = [row]

    finalize_cluster(cluster)

    # Persist newly detected stops.
    # Existing records are reused. If a detected stop has the same
    # start point/time, extend the existing record instead of inserting
    # a duplicate.
    for item in detected:
        existing = (
            db.query(GpsVehicleStop)
            .filter(
                GpsVehicleStop.vehicle_id == vehicle_id,
                GpsVehicleStop.start_at >= (
                    item["start_at"] - timedelta(seconds=60)
                ),
                GpsVehicleStop.start_at <= (
                    item["start_at"] + timedelta(seconds=60)
                ),
            )
            .order_by(GpsVehicleStop.start_at)
            .first()
        )

        if existing:
            if item["end_at"] > existing.end_at:
                existing.end_at = item["end_at"]
                existing.duration_seconds = int(
                    (existing.end_at - existing.start_at).total_seconds()
                )
                existing.point_count = max(
                    int(existing.point_count or 0),
                    int(item["point_count"]),
                )

            continue

        geo = reverse_geocode(
            item["latitude"],
            item["longitude"],
        )

        db.add(
            GpsVehicleStop(
                vehicle_id=vehicle_id,
                start_at=item["start_at"],
                end_at=item["end_at"],
                duration_seconds=item["duration_seconds"],
                latitude=item["latitude"],
                longitude=item["longitude"],
                address=geo.get("display_name") or "",
                road=geo.get("road") or "",
                house_number=geo.get("house_number") or "",
                city=geo.get("city") or "",
                state=geo.get("state") or "",
                country=geo.get("country") or "",
                point_count=item["point_count"],
            )
        )

    db.commit()

    # Return persistent history. Raw GPS is used only for detecting
    # new/ongoing stops; already saved stops come directly from DB.
    saved_rows = (
        db.query(GpsVehicleStop)
        .filter(
            GpsVehicleStop.vehicle_id == vehicle_id,
            GpsVehicleStop.start_at <= end_utc,
            GpsVehicleStop.end_at >= start_utc,
        )
        .order_by(
            GpsVehicleStop.start_at,
            GpsVehicleStop.id,
        )
        .all()
    )

    stops = [
        {
            "id": stop.id,
            "start_at": stop.start_at.isoformat(),
            "end_at": stop.end_at.isoformat(),
            "duration_seconds": int(stop.duration_seconds),
            "latitude": round(float(stop.latitude), 7),
            "longitude": round(float(stop.longitude), 7),
            "address": stop.address or "",
            "road": stop.road or "",
            "house_number": stop.house_number or "",
            "city": stop.city or "",
            "state": stop.state or "",
            "country": stop.country or "",
            "point_count": int(stop.point_count or 0),
        }
        for stop in saved_rows
    ]

    return {
        "vehicle_id": vehicle_id,
        "registration_number": vehicle.registration_number,
        "from": start_utc.isoformat(),
        "to": end_utc.isoformat(),
        "min_stop_seconds": min_stop_seconds,
        "stop_count": len(stops),
        "stops": stops,
    }


@router.get("/tracking/policy")
def tracking_policy(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    if not (user_has_permission(db,user,"gps_trip_track") or user_has_permission(db,user,"gps_trip_view")):raise HTTPException(403,detail={"code":"permission_denied"})
    return gps_policy(db)

@router.put("/tracking/policy")
def tracking_policy_save(data:GpsPolicyUpdate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    if not user_has_permission(db,user,"platform_admin_security"):raise HTTPException(403,detail={"code":"permission_denied"})
    try:
        values=validate_policy(data.model_dump(exclude={"version"}));result=put_versioned_setting(db,"platform.integration.gps",values,data.version);log_action(db,user.username,"gps_policy_update","platform_setting",None,"canonical keys updated");db.commit();return result
    except TripTrackingError as exc:db.rollback();_error(exc)




