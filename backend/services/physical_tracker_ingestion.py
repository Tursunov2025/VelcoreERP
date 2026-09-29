"""Shared canonical device/session resolution for physical tracker adapters."""
from __future__ import annotations

import logging
from datetime import datetime

from models import GpsAlertState, MesGpsDevice, MesTrip, MesTripTrackingSession
from services.trip_tracking import TRACKABLE_STATUSES, append_locations_for_session
from services.gps_fleet import save_location

logger = logging.getLogger("velcore.physical_tracker")


class PhysicalTrackerError(RuntimeError):
    pass


def resolve_device(db, identifier: str):
    device = db.query(MesGpsDevice).filter_by(device_identifier=identifier).first()
    if not device:
        logger.warning("Rejected unknown physical tracker identifier suffix=%s", identifier[-4:])
        raise PhysicalTrackerError("unknown GPS device")
    if device.status != "active":
        raise PhysicalTrackerError("GPS device is inactive")
    if not device.vehicle_id:
        raise PhysicalTrackerError("GPS device has no vehicle binding")
    return device


def resolve_active_session(db, device):
    now = datetime.utcnow()
    query = (db.query(MesTripTrackingSession)
             .join(MesTrip, MesTrip.id == MesTripTrackingSession.trip_id)
             .filter(MesTripTrackingSession.device_id == device.id,
                     MesTripTrackingSession.vehicle_id == device.vehicle_id,
                     MesTripTrackingSession.status == "active",
                     MesTripTrackingSession.authorization_expires_at > now,
                     MesTrip.status.in_(TRACKABLE_STATUSES)))
    if device.driver_user_id is not None:
        query = query.filter(MesTripTrackingSession.driver_user_id == device.driver_user_id)
    sessions = query.with_for_update().all()
    if not sessions:
        raise PhysicalTrackerError("no active tracking session")
    if len(sessions) != 1:
        raise PhysicalTrackerError("multiple active tracking sessions")
    session = sessions[0]
    if session.trip.vehicle_id != device.vehicle_id or session.trip.driver_user_id != session.driver_user_id:
        raise PhysicalTrackerError("tracking session identity mismatch")
    return session


class PhysicalTrackerIngestor:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def validate_device(self, identifier: str) -> None:
        db = self.session_factory()
        try:
            resolve_device(db, identifier)
        finally:
            db.close()

    def ingest(self, identifier: str, points: list[dict]) -> dict:
        db = self.session_factory()
        try:
            device = resolve_device(db, identifier)

            try:
                session = resolve_active_session(db, device)
            except PhysicalTrackerError as exc:
                if str(exc) != "no active tracking session":
                    raise
                session = None

            # Normal trip tracking remains authoritative when a trip/session exists.
            if session is not None:
                result = append_locations_for_session(db, session, points)

                if points:
                    newest = max(points, key=lambda p: p["captured_at"])
                    captured_at = newest["captured_at"].replace(tzinfo=None)
                    device.last_seen_at = datetime.utcnow()

                    if (
                        device.last_captured_at is None
                        or captured_at >= device.last_captured_at
                    ):
                        device.last_latitude = newest.get("latitude")
                        device.last_longitude = newest.get("longitude")
                        device.last_speed_kmh = newest.get("speed_kmh")
                        device.last_heading_deg = newest.get("heading_deg")
                        device.last_captured_at = captured_at

                db.commit()
                return result

            # No trip is active: keep the physical vehicle's latest position alive.
            if not points:
                now = datetime.utcnow()
                device.last_seen_at = now
                db.commit()
                return {
                    "accepted": 0,
                    "duplicates": 0,
                    "received_at": now,
                    "latest": None,
                    "mode": "vehicle_latest",
                }

            newest = max(points, key=lambda p: p["captured_at"])
            captured_at = newest["captured_at"].replace(tzinfo=None)
            latitude = float(newest["latitude"])
            longitude = float(newest["longitude"])

            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise PhysicalTrackerError("GPS coordinates are out of range")

            now = datetime.utcnow()
            device.last_seen_at = now

            is_newest_live_point = (
                device.last_captured_at is None
                or captured_at >= device.last_captured_at
            )

            if is_newest_live_point:
                device.last_latitude = latitude
                device.last_longitude = longitude
                device.last_speed_kmh = newest.get("speed_kmh")
                device.last_heading_deg = newest.get("heading_deg")
                device.last_captured_at = captured_at

            alert_state = db.query(GpsAlertState).filter(
                GpsAlertState.vehicle_id == device.vehicle_id
            ).first()

            if not alert_state:
                alert_state = GpsAlertState(vehicle_id=device.vehicle_id)
                db.add(alert_state)
                db.flush()

            current_speed = float(newest.get("speed_kmh") or 0)
            speed_limit = alert_state.speed_limit_kmh

            if speed_limit is not None and current_speed > float(speed_limit):
                if not alert_state.overspeed_alert_sent:
                    logger.warning(
                        "OVERSPEED vehicle_id=%s device=%s speed=%.1f limit=%.1f",
                        device.vehicle_id,
                        device.device_identifier,
                        current_speed,
                        float(speed_limit),
                    )
                    alert_state.overspeed_alert_sent = 1
            elif alert_state.overspeed_alert_sent:
                alert_state.overspeed_alert_sent = 0

            if (
                alert_state.geofence_enabled
                and alert_state.geofence_latitude is not None
                and alert_state.geofence_longitude is not None
                and alert_state.geofence_radius_m is not None
            ):
                from services.gps_geocode import haversine_meters

                distance_from_center = haversine_meters(
                    float(alert_state.geofence_latitude),
                    float(alert_state.geofence_longitude),
                    float(latitude),
                    float(longitude),
                )

                if distance_from_center > float(alert_state.geofence_radius_m):
                    if not alert_state.geofence_outside_alert_sent:
                        logger.warning(
                            "GEOFENCE EXIT vehicle_id=%s device=%s distance=%.1fm radius=%.1fm",
                            device.vehicle_id,
                            device.device_identifier,
                            distance_from_center,
                            float(alert_state.geofence_radius_m),
                        )
                        alert_state.geofence_outside_alert_sent = 1
                elif alert_state.geofence_outside_alert_sent:
                    logger.info(
                        "GEOFENCE ENTER vehicle_id=%s device=%s distance=%.1fm",
                        device.vehicle_id,
                        device.device_identifier,
                        distance_from_center,
                    )
                    alert_state.geofence_outside_alert_sent = 0

            alert_state.updated_at = now

            save_location(
                db,
                vehicle_id=device.vehicle_id,
                driver_id=None,
                latitude=latitude,
                longitude=longitude,
                speed=float(newest.get("speed_kmh") or 0),
                battery_level=None,
                recorded_at=captured_at,
            )

            db.commit()

            logger.info(
                "Physical tracker latest position accepted without trip device_id=%s vehicle_id=%s",
                device.id,
                device.vehicle_id,
            )

            return {
                "accepted": len(points),
                "duplicates": 0,
                "received_at": now,
                "latest": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "speed_kmh": device.last_speed_kmh,
                    "heading_deg": device.last_heading_deg,
                    "captured_at": newest.get("captured_at"),
                },
                "mode": "vehicle_latest",
            }
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def heartbeat(self, identifier: str) -> None:
        db = self.session_factory()
        try:
            device = resolve_device(db, identifier)
            now = datetime.utcnow()

            try:
                session = resolve_active_session(db, device)
            except PhysicalTrackerError as exc:
                if str(exc) != "no active tracking session":
                    raise
                session = None

            device.last_seen_at = now

            if session is not None:
                session.last_contact_at = now
                session.health_state = "active"

            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
