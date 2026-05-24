from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from constants import PRODUCTION_STAGES
from database import get_db
from models import Order, OrderHistory, User

router = APIRouter(prefix="/production", tags=["production"])


@router.get("/timeline/{order_id}")
def order_timeline(
    order_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return (
        db.query(OrderHistory)
        .filter(OrderHistory.order_id == order_id)
        .order_by(OrderHistory.completed_at.asc())
        .all()
    )


@router.get("/analytics")
def stage_analytics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    orders = db.query(Order).filter(Order.in_warehouse.is_(False)).all()
    by_stage = Counter(o.status for o in orders)
    return {
        "stages": [s for s in PRODUCTION_STAGES if s != "Tayyor"],
        "counts": {stage: by_stage.get(stage, 0) for stage in PRODUCTION_STAGES},
        "total_orders": len(orders),
        "in_production": sum(1 for o in orders if o.status != "Tayyor"),
        "completed": by_stage.get("Tayyor", 0),
    }


@router.get("/active")
def active_production(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Order).filter(
        Order.in_warehouse.is_(False),
        Order.status != "Tayyor",
    )
    if user.role != "admin" and user.department not in ("Admin", "Ombor"):
        query = query.filter(Order.status == user.department)
    return query.order_by(Order.updated_at.desc()).all()
