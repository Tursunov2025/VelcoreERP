"""GPS fleet Telegram alerts — offline, destination city, border crossing."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from models import Driver, GpsAlertState, GpsLocation, MesGpsDevice, MesVehicle, TripRoute, Vehicle
from services.gps_fleet import latest_location_for_vehicle
from services.gps_geocode import city_matches_destination, reverse_geocode
from services.telegram import (
    format_gps_border_alert,
    format_gps_destination_alert,
    format_gps_geofence_alert,
    format_gps_overspeed_alert,
    format_gps_offline_alert,
    send_telegram_message,
)

logger = logging.getLogger("azmus.gps_alerts")

OFFLINE_ALERT_MINUTES = 10
ACTIVE_TRIP_STATUSES = ("Planned", "Active", "In Transit")


def _alert_state(db: Session, vehicle_id: int) -> GpsAlertState:
    row = db.query(GpsAlertState).filter(GpsAlertState.vehicle_id == vehicle_id).first()
    if not row:
        row = GpsAlertState(vehicle_id=vehicle_id)
        db.add(row)
        db.flush()
    return row


def mark_vehicle_online(db: Session, vehicle_id: int) -> None:
    state = _alert_state(db, vehicle_id)
    state.offline_alert_sent = False
    state.updated_at = datetime.utcnow()


async def _notify(db: Session, text: str, driver: Driver | None) -> None:
    await send_telegram_message(text, db=db)
    if driver and driver.telegram_username:
        # Direct message requires chat_id; username stored for future bot linking
        pass


async def run_gps_alerts_job(db: Session | None = None) -> dict:
    from database import SessionLocal

    own = db is None
    if own:
        db = SessionLocal()

    sent = 0
    checked = 0
    now = datetime.utcnow()
    offline_cutoff = now - timedelta(minutes=OFFLINE_ALERT_MINUTES)

    try:
        trips = (
            db.query(TripRoute)
            .options(joinedload(TripRoute.vehicle), joinedload(TripRoute.driver))
            .filter(TripRoute.status.in_(ACTIVE_TRIP_STATUSES))
            .all()
        )
        for trip in trips:
            checked += 1
            loc = latest_location_for_vehicle(db, trip.vehicle_id)
            vehicle = trip.vehicle or db.query(Vehicle).filter(Vehicle.id == trip.vehicle_id).first()
            driver = trip.driver
            if not vehicle:
                continue

            state = _alert_state(db, trip.vehicle_id)
            plate = vehicle.plate_number

            # Offline > 10 min
            if loc is None or (loc.recorded_at and loc.recorded_at < offline_cutoff):
                if not state.offline_alert_sent:
                    age_min = OFFLINE_ALERT_MINUTES
                    if loc and loc.recorded_at:
                        age_min = int((now - loc.recorded_at).total_seconds() / 60)
                    text = format_gps_offline_alert(plate, driver, age_min, trip.destination)
                    if await _notify(db, text, driver):
                        state.offline_alert_sent = True
                        sent += 1
                continue

            if not loc:
                continue

            geo = reverse_geocode(loc.latitude, loc.longitude)
            city = geo.get("city") or ""
            country = geo.get("country") or ""
            cc = geo.get("country_code") or ""

            # Destination city entered
            dest = (trip.destination or "").strip()
            if dest and city and not state.destination_alert_sent:
                if city_matches_destination(city, dest):
                    text = format_gps_destination_alert(plate, driver, city, dest)
                    if await _notify(db, text, driver):
                        state.destination_alert_sent = True
                        sent += 1

            # Border crossing — country changed from UZ
            prev_country = (state.last_country or "").upper()
            if cc and prev_country and cc != prev_country and not state.border_alert_sent:
                if prev_country == "UZ" or cc != "UZ":
                    text = format_gps_border_alert(
                        plate, driver, prev_country, cc, city or country
                    )
                    if await _notify(db, text, driver):
                        state.border_alert_sent = True
                        sent += 1

            if (
                state.geofence_enabled
                and state.geofence_latitude is not None
                and state.geofence_longitude is not None
                and state.geofence_radius_m is not None
            ):
                from services.gps_geocode import haversine_meters

                distance_m = haversine_meters(
                    float(state.geofence_latitude),
                    float(state.geofence_longitude),
                    float(loc.latitude),
                    float(loc.longitude),
                )

                if distance_m > float(state.geofence_radius_m):
                    if not state.geofence_telegram_alert_sent:
                        text = format_gps_geofence_alert(
                            plate,
                            driver,
                            distance_m,
                            float(state.geofence_radius_m),
                            float(loc.latitude),
                            float(loc.longitude),
                        )
                        await _notify(db, text, driver)
                        state.geofence_telegram_alert_sent = 1
                        sent += 1
                elif state.geofence_telegram_alert_sent:
                    state.geofence_telegram_alert_sent = 0

            state.last_city = city
            state.last_country = cc or country
            state.updated_at = now

        # Canonical physical GPS devices — geofence works even without a trip
        devices = (
            db.query(MesGpsDevice)
            .filter(MesGpsDevice.status == "active")
            .all()
        )

        for device in devices:
            if (
                device.vehicle_id is None
                or device.last_latitude is None
                or device.last_longitude is None
            ):
                continue

            state = _alert_state(db, device.vehicle_id)

            vehicle = (
                device.vehicle
                or db.query(MesVehicle)
                .filter(MesVehicle.id == device.vehicle_id)
                .first()
            )
            plate = vehicle.registration_number if vehicle else str(device.vehicle_id)

            checked += 1

            # Overspeed Telegram alert
            current_speed = float(device.last_speed_kmh or 0)
            if state.speed_limit_kmh is not None:
                speed_limit = float(state.speed_limit_kmh)

                if current_speed > speed_limit:
                    if not state.overspeed_telegram_alert_sent:
                        text = format_gps_overspeed_alert(
                            plate,
                            None,
                            current_speed,
                            speed_limit,
                            float(device.last_latitude),
                            float(device.last_longitude),
                        )
                        await _notify(db, text, None)
                        state.overspeed_telegram_alert_sent = 1
                        state.updated_at = now
                        sent += 1
                elif state.overspeed_telegram_alert_sent:
                    state.overspeed_telegram_alert_sent = 0
                    state.updated_at = now

            # Geofence Telegram alert
            if (
                state.geofence_enabled
                and state.geofence_latitude is not None
                and state.geofence_longitude is not None
                and state.geofence_radius_m is not None
            ):
                from services.gps_geocode import haversine_meters

                distance_m = haversine_meters(
                    float(state.geofence_latitude),
                    float(state.geofence_longitude),
                    float(device.last_latitude),
                    float(device.last_longitude),
                )

                if distance_m > float(state.geofence_radius_m):
                    if not state.geofence_telegram_alert_sent:
                        text = format_gps_geofence_alert(
                            plate,
                            None,
                            distance_m,
                            float(state.geofence_radius_m),
                            float(device.last_latitude),
                            float(device.last_longitude),
                        )
                        await _notify(db, text, None)
                        state.geofence_telegram_alert_sent = 1
                        state.updated_at = now
                        sent += 1
                elif state.geofence_telegram_alert_sent:
                    state.geofence_telegram_alert_sent = 0
                    state.updated_at = now

        db.commit()
    except Exception:
        logger.exception("gps alerts job failed")
        db.rollback()
    finally:
        if own:
            db.close()

    return {"checked": checked, "sent": sent}


def run_gps_alerts_sync() -> None:
    try:
        asyncio.run(run_gps_alerts_job())
    except Exception:
        logger.exception("gps alerts sync wrapper failed")
