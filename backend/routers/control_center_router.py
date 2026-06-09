"""Executive control center — unified orders/jobs and UI config."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from auth.deps import get_current_user, require_admin
from database import get_db
from models import User
from services.control_center_config import (
    get_dashboard_widgets,
    get_mobile_app_config,
    get_nav_visibility,
)
from services.feature_flags import print_agent_enabled, traceability_enabled
from services.orders_control_center import export_items_csv, list_control_center_items
from services.settings_store import get_settings_for_admin

router = APIRouter(prefix="/control-center", tags=["control-center"])


@router.get("/config/ui")
def get_ui_config(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Nav visibility + dashboard widgets for all authenticated users."""
    settings = get_settings_for_admin(db)
    return {
        "nav_visibility": get_nav_visibility(settings),
        "dashboard_widgets": get_dashboard_widgets(settings),
        "mobile_app": get_mobile_app_config(settings) if user.role == "admin" or user.department == "Admin" else None,
        "feature_flags": {
            "traceability_enabled": traceability_enabled(),
            "print_agent_enabled": print_agent_enabled(),
        },
    }


@router.get("/orders")
def control_center_orders(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    q: str = Query(""),
    customer: str = Query(""),
    status: str = Query(""),
    type: str = Query("all", alias="type"),
    delayed_only: bool = Query(False),
    limit: int = Query(500, le=1000),
):
    return list_control_center_items(
        db,
        q=q,
        customer=customer,
        status=status,
        item_type=type,
        delayed_only=delayed_only,
        limit=limit,
    )


@router.get("/orders/export.csv")
def export_control_center_csv(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    q: str = Query(""),
    customer: str = Query(""),
    status: str = Query(""),
    type: str = Query("all", alias="type"),
    delayed_only: bool = Query(False),
):
    data = list_control_center_items(
        db,
        q=q,
        customer=customer,
        status=status,
        item_type=type,
        delayed_only=delayed_only,
        limit=5000,
    )
    csv_text = export_items_csv(data["items"])
    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="orders-control-center.csv"'},
    )
