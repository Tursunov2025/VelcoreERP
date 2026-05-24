from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import Expense, Income, Order, User
from schemas import PRODUCTION_STAGES

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
def dashboard_analytics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    orders = db.query(Order).all()
    expenses = db.query(Expense).all()
    incomes = db.query(Income).all()

    total_revenue = sum(float(o.amount or 0) for o in orders)
    total_income = sum(i.amount for i in incomes)
    total_expenses = sum(e.amount for e in expenses)
    net_profit = total_income - total_expenses

    monthly_sales = defaultdict(float)
    for order in orders:
        if order.created_at:
            key = order.created_at.strftime("%Y-%m")
            monthly_sales[key] += float(order.amount or 0)

    stage_counts = {s: 0 for s in PRODUCTION_STAGES}
    for order in orders:
        if order.status in stage_counts:
            stage_counts[order.status] += 1

    return {
        "summary": {
            "total_orders": len(orders),
            "completed_orders": sum(1 for o in orders if o.status == "Tayyor"),
            "active_orders": sum(1 for o in orders if o.status != "Tayyor"),
            "total_revenue": total_revenue,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
        },
        "monthly_sales": [
            {"month": k, "sales": v}
            for k, v in sorted(monthly_sales.items())
        ],
        "production_stats": [
            {"stage": s, "count": stage_counts[s]} for s in PRODUCTION_STAGES
        ],
        "revenue_chart": [
            {"name": "Daromad", "value": total_income},
            {"name": "Xarajat", "value": total_expenses},
            {"name": "Foyda", "value": max(net_profit, 0)},
        ],
    }
