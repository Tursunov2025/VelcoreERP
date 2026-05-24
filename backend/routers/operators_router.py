from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import Order, User

router = APIRouter(prefix="/operators", tags=["operators"])


@router.get("/stats")
def operator_statistics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    orders = db.query(Order).all()
    users = {u.id: u.username for u in db.query(User).all()}

    stats = defaultdict(lambda: {"completed": 0, "active": 0, "total": 0})

    for order in orders:
        key = users.get(order.operator_id, "Noma'lum")
        stats[key]["total"] += 1
        if order.status == "Tayyor":
            stats[key]["completed"] += 1
        else:
            stats[key]["active"] += 1

    rankings = sorted(
        [
            {
                "operator": name,
                "completed": data["completed"],
                "active": data["active"],
                "total": data["total"],
                "performance": round(
                    (data["completed"] / data["total"] * 100) if data["total"] else 0,
                    1,
                ),
            }
            for name, data in stats.items()
        ],
        key=lambda x: x["completed"],
        reverse=True,
    )

    return {"operators": rankings}
