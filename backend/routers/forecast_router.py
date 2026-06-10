"""Phase 11B — Warehouse consumption forecasting and low-stock alerts.

Forecast is computed (no new tables): daily consumption is averaged from
material issues + automatic MES consumptions over a trailing window.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from auth.deps import get_current_user
from database import get_db
from models import Material, MaterialConsumption, MaterialIssue, User
from services.permissions import user_has_permission

router = APIRouter(prefix="/warehouse-forecast", tags=["warehouse-forecast"])

WINDOW_DAYS = 30
LOW_STOCK_DAYS = 14


def _can_view(db: Session, user: User) -> bool:
    return (
        user.role == "admin"
        or user_has_permission(db, user, "materials_view")
        or user_has_permission(db, user, "warehouse")
    )


def _consumption_totals(db: Session, since: datetime) -> dict[int, float]:
    totals: dict[int, float] = {}
    issue_rows = (
        db.query(MaterialIssue.material_id, func.coalesce(func.sum(MaterialIssue.quantity), 0))
        .filter(MaterialIssue.created_at >= since)
        .group_by(MaterialIssue.material_id)
        .all()
    )
    for material_id, qty in issue_rows:
        totals[material_id] = totals.get(material_id, 0.0) + float(qty or 0)
    consumption_rows = (
        db.query(
            MaterialConsumption.material_id,
            func.coalesce(func.sum(MaterialConsumption.quantity), 0),
        )
        .filter(MaterialConsumption.consumed_at >= since)
        .group_by(MaterialConsumption.material_id)
        .all()
    )
    for material_id, qty in consumption_rows:
        totals[material_id] = totals.get(material_id, 0.0) + float(qty or 0)
    return totals


def build_forecast(db: Session) -> list[dict]:
    now = datetime.utcnow()
    full_window = _consumption_totals(db, now - timedelta(days=WINDOW_DAYS))
    recent_half = _consumption_totals(db, now - timedelta(days=WINDOW_DAYS // 2))

    materials = (
        db.query(Material)
        .options(selectinload(Material.category))
        .filter(Material.is_active.is_(True))
        .order_by(Material.name)
        .all()
    )

    rows = []
    for material in materials:
        consumed = full_window.get(material.id, 0.0)
        recent = recent_half.get(material.id, 0.0)
        earlier = consumed - recent
        daily = consumed / WINDOW_DAYS
        days_remaining = None
        if daily > 0:
            days_remaining = round((material.quantity or 0) / daily, 1)

        if recent > earlier * 1.15:
            trend = "up"
        elif recent < earlier * 0.85:
            trend = "down"
        else:
            trend = "stable"
        if consumed == 0:
            trend = "none"

        low_stock = bool(
            (material.min_quantity and (material.quantity or 0) <= material.min_quantity)
            or (days_remaining is not None and days_remaining <= LOW_STOCK_DAYS)
        )
        rows.append(
            {
                "material_id": material.id,
                "code": material.code,
                "name": material.name,
                "unit": material.unit,
                "category": material.category.name if material.category else None,
                "quantity": material.quantity,
                "min_quantity": material.min_quantity,
                "consumed_30d": round(consumed, 2),
                "avg_daily_consumption": round(daily, 3),
                "days_remaining": days_remaining,
                "trend": trend,
                "low_stock": low_stock,
            }
        )

    rows.sort(
        key=lambda r: (
            r["days_remaining"] if r["days_remaining"] is not None else float("inf"),
            -r["consumed_30d"],
        )
    )
    return rows


@router.get("/")
def warehouse_forecast(
    category: str = Query(default=""),
    low_stock_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_view(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = build_forecast(db)
    if category:
        needle = category.lower()
        rows = [r for r in rows if (r["category"] or "").lower().find(needle) >= 0]
    if low_stock_only:
        rows = [r for r in rows if r["low_stock"]]
    return {
        "window_days": WINDOW_DAYS,
        "low_stock_threshold_days": LOW_STOCK_DAYS,
        "items": rows,
    }


@router.get("/alerts")
def low_stock_alerts(
    limit: int = Query(default=8, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_view(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = [r for r in build_forecast(db) if r["low_stock"]]
    return {"alerts": rows[:limit], "total_low_stock": len(rows)}
