from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import User
from services.mes_production_monitor import list_monitor_jobs, monitor_dashboard
from services.permissions import user_has_permission

router = APIRouter(prefix="/mes/monitor", tags=["mes-monitor"])


def _require_monitor_view(db: Session, user: User) -> None:
    if user_has_permission(db, user, "mes_view") or user_has_permission(
        db, user, "mes_jobs_view"
    ):
        return
    raise HTTPException(status_code=403, detail="Permission required: mes_view")


@router.get("/dashboard")
def get_monitor_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_monitor_view(db, user)
    return monitor_dashboard(db)


@router.get("/jobs")
def get_monitor_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    stage: str = Query(""),
    customer: str = Query(""),
    priority: Optional[str] = Query(None),
):
    _require_monitor_view(db, user)
    jobs = list_monitor_jobs(
        db,
        stage=stage,
        customer=customer,
        priority=priority or "",
    )
    return {"jobs": jobs}
