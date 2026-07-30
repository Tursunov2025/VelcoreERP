"""Haydovchi joriy joylashuvi — upsert va admin live ro'yxat."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from models import Driver, DriverLocation


def upsert_driver_location(
    db: Session,
    driver_id: int,
    latitude: float,
    longitude: float,
    status: str = "active",
) -> DriverLocation:
    now = datetime.utcnow()
    row = db.query(DriverLocation).filter(DriverLocation.driver_id == driver_id).first()
    if row:
        row.latitude = latitude
        row.longitude = longitude
        row.status = status or "active"
        row.last_updated = now
    else:
        row = DriverLocation(
            driver_id=driver_id,
            latitude=latitude,
            longitude=longitude,
            status=status or "active",
            last_updated=now,
        )
        db.add(row)
    db.flush()
    return row


def list_live_drivers(db: Session, max_age_minutes: int = 5) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
    rows = (
        db.query(DriverLocation)
        .options(joinedload(DriverLocation.driver))
        .join(Driver, DriverLocation.driver_id == Driver.id)
        .filter(
            DriverLocation.last_updated >= cutoff,
            DriverLocation.status != "offline",
        )
        .order_by(DriverLocation.last_updated.desc())
        .all()
    )
    result = []
    for loc in rows:
        driver = loc.driver
        result.append(
            {
                "driver_id": loc.driver_id,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "status": loc.status,
                "last_updated": loc.last_updated.isoformat() if loc.last_updated else None,
                "name": driver.full_name if driver else "",
                "phone": driver.phone if driver else "",
                "driver_type": getattr(driver, "driver_type", None) or "internal",
                "default_vehicle_id": getattr(driver, "default_vehicle_id", None),
            }
        )
    return result
