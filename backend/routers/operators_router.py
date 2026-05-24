from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import Order, OrderHistory, User
from services.activity import get_online_operators

router = APIRouter(prefix="/operators", tags=["operators"])


@router.get("/online")
def online_operators(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return {"operators": get_online_operators(db)}


@router.get("/stats")
def operator_statistics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    history = db.query(OrderHistory).filter(OrderHistory.action == "completed").all()
    stats = defaultdict(lambda: {"completed": 0, "stages": defaultdict(int)})

    for entry in history:
        key = entry.operator_username
        stats[key]["completed"] += 1
        stats[key]["stages"][entry.stage] += 1

    rankings = sorted(
        [
            {
                "operator": name,
                "completed": data["completed"],
                "stages": dict(data["stages"]),
            }
            for name, data in stats.items()
        ],
        key=lambda x: x["completed"],
        reverse=True,
    )
    return {"operators": rankings}
