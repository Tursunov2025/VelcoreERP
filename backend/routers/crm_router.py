"""Phase 11B — Customer ledger and debt tracking."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import CustomerPayment, Order, User
from routers.currency_router import convert_amount
from services.audit import log_action
from services.permissions import user_has_permission

router = APIRouter(prefix="/crm", tags=["crm"])


def _can_view(db: Session, user: User) -> bool:
    return (
        user.role == "admin"
        or user_has_permission(db, user, "finance")
        or user_has_permission(db, user, "orders")
    )


def _can_manage(db: Session, user: User) -> bool:
    return user.role == "admin" or user_has_permission(db, user, "finance")


def parse_amount(raw: str | None) -> float:
    if not raw:
        return 0.0
    cleaned = re.sub(r"[^\d.,-]", "", str(raw)).replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


class PaymentIn(BaseModel):
    customer: str
    amount: float = Field(gt=0)
    currency: str = "UZS"
    order_id: int | None = None
    notes: str = ""


def build_ledger(db: Session) -> list[dict]:
    """Per-customer totals in base currency (UZS)."""
    ledger: dict[str, dict] = {}
    orders = db.query(Order).filter(Order.deleted_at.is_(None)).all()
    for order in orders:
        entry = ledger.setdefault(
            order.client,
            {
                "customer": order.client,
                "orders_count": 0,
                "total_orders": 0.0,
                "paid_amount": 0.0,
                "currency": "UZS",
            },
        )
        entry["orders_count"] += 1
        amount = parse_amount(order.amount)
        converted = convert_amount(db, amount, order.currency or "UZS", "UZS")
        entry["total_orders"] += converted if converted is not None else amount

    for payment in db.query(CustomerPayment).all():
        entry = ledger.setdefault(
            payment.customer,
            {
                "customer": payment.customer,
                "orders_count": 0,
                "total_orders": 0.0,
                "paid_amount": 0.0,
                "currency": "UZS",
            },
        )
        converted = convert_amount(db, payment.amount, payment.currency or "UZS", "UZS")
        entry["paid_amount"] += converted if converted is not None else payment.amount

    rows = []
    for entry in ledger.values():
        entry["total_orders"] = round(entry["total_orders"], 2)
        entry["paid_amount"] = round(entry["paid_amount"], 2)
        entry["outstanding_debt"] = round(entry["total_orders"] - entry["paid_amount"], 2)
        rows.append(entry)
    rows.sort(key=lambda r: r["outstanding_debt"], reverse=True)
    return rows


@router.get("/ledger")
def customer_ledger(
    q: str = Query(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_view(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = build_ledger(db)
    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in r["customer"].lower()]
    return {"currency": "UZS", "ledger": rows}


@router.get("/top-debtors")
def top_debtors(
    limit: int = Query(default=5, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_view(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = [r for r in build_ledger(db) if r["outstanding_debt"] > 0]
    return {"currency": "UZS", "debtors": rows[:limit]}


@router.get("/payments")
def list_payments(
    customer: str = Query(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_view(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    query = db.query(CustomerPayment)
    if customer:
        query = query.filter(CustomerPayment.customer == customer)
    payments = query.order_by(desc(CustomerPayment.created_at)).limit(300).all()
    return {
        "payments": [
            {
                "id": p.id,
                "customer": p.customer,
                "order_id": p.order_id,
                "amount": p.amount,
                "currency": p.currency,
                "notes": p.notes,
                "created_by": p.created_by,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in payments
        ]
    }


@router.post("/payments")
def record_payment(
    payload: PaymentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_manage(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    if payload.order_id is not None:
        order = db.query(Order).filter(Order.id == payload.order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
    payment = CustomerPayment(
        customer=payload.customer.strip(),
        order_id=payload.order_id,
        amount=payload.amount,
        currency=payload.currency.upper(),
        notes=payload.notes,
        created_by=user.username,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    log_action(
        db,
        user.username,
        "customer_payment",
        f"{payment.customer}: {payment.amount} {payment.currency}",
    )
    return {"id": payment.id, "status": "ok"}
