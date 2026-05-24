from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import Order, ProductionLog, User
from schemas import PRODUCTION_STAGES, ProductionLogResponse

router = APIRouter(prefix="/production", tags=["production"])


@router.get("/timeline/{order_id}", response_model=list[ProductionLogResponse])
def order_timeline(
    order_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return (
        db.query(ProductionLog)
        .filter(ProductionLog.order_id == order_id)
        .order_by(ProductionLog.created_at.asc())
        .all()
    )


@router.get("/analytics")
def stage_analytics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    orders = db.query(Order).all()
    by_stage = Counter(o.status for o in orders)
    return {
        "stages": PRODUCTION_STAGES,
        "counts": {stage: by_stage.get(stage, 0) for stage in PRODUCTION_STAGES},
        "total_orders": len(orders),
        "in_production": sum(
            1 for o in orders if o.status not in ("Yangi", "Tayyor")
        ),
        "completed": by_stage.get("Tayyor", 0),
    }


@router.get("/active")
def active_production(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    orders = (
        db.query(Order)
        .filter(Order.status != "Tayyor")
        .order_by(Order.updated_at.desc())
        .all()
    )
    return orders
