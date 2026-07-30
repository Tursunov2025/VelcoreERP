"""Haydovchi joylashuvi — real vaqt upsert va admin live ko'rinish."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import Driver, User
from routers.driver_router import _find_driver_for_user, _require_driver
from services.audit import log_action
from services.driver_location_service import list_live_drivers, upsert_driver_location
from services.gps_alerts import mark_vehicle_online
from services.gps_fleet import save_location
from services.permissions import user_has_permission

router = APIRouter(tags=["driver-locations"])


class DriverLocationIn(BaseModel):
    driver_id: int
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    status: str = "active"


class DriverLocationSelfIn(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    status: str = "active"


def _can_view_live_drivers(db: Session, user: User) -> bool:
    if user.role == "admin":
        return True
    if user.department in ("Admin", "Logistika"):
        return True
    return user_has_permission(db, user, "export_view")


@router.post("/api/driver/location")
def update_driver_location(
    payload: DriverLocationIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Haydovchi koordinatasini qabul qilish va yangilash (upsert)."""
    if not payload.driver_id or payload.latitude is None or payload.longitude is None:
        raise HTTPException(status_code=400, detail="Ma'lumotlar to'liq emas")

    driver = db.query(Driver).filter(Driver.id == payload.driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Haydovchi topilmadi")

    linked = _find_driver_for_user(db, user)
    if user.role != "admin" and user.department not in ("Admin", "Logistika"):
        if not linked or linked.id != payload.driver_id:
            raise HTTPException(status_code=403, detail="Faqat o'z joylashuvingizni yangilashingiz mumkin")

    try:
        upsert_driver_location(
            db,
            driver_id=payload.driver_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            status=payload.status or "active",
        )

        # Fleet xaritasi bilan sinxron — agar transport biriktirilgan bo'lsa
        vehicle_id = getattr(driver, "default_vehicle_id", None)
        if vehicle_id:
            save_location(
                db,
                vehicle_id=vehicle_id,
                driver_id=payload.driver_id,
                latitude=payload.latitude,
                longitude=payload.longitude,
                speed=0,
                battery_level=None,
            )
            mark_vehicle_online(db, vehicle_id)

        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Bazaga yozishda xatolik") from exc

    log_action(
        db,
        user.username,
        "driver_location_update",
        f"driver={payload.driver_id} lat={payload.latitude}",
    )
    return {"success": True, "message": "Joylashuv yangilandi"}


@router.post("/driver/location")
def update_driver_location_alias(
    payload: DriverLocationIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Alias: POST /api/driver/location"""
    return update_driver_location(payload, db, user)


@router.post("/driver/location/me")
def update_my_driver_location(
    payload: DriverLocationSelfIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mobil ilova — JWT orqali haydovchi ID avtomatik."""
    driver = _require_driver(db, user)
    return update_driver_location(
        DriverLocationIn(
            driver_id=driver.id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            status=payload.status,
        ),
        db,
        user,
    )


@router.get("/api/admin/drivers-live")
def admin_drivers_live(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Admin panel — oxirgi 5 daqiqada faol haydovchilar."""
    if not _can_view_live_drivers(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"success": True, "drivers": list_live_drivers(db)}


@router.get("/admin/drivers-live")
def admin_drivers_live_alias(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Alias: GET /api/admin/drivers-live"""
    if not _can_view_live_drivers(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"success": True, "drivers": list_live_drivers(db)}
