"""Phase 11B — Multi Currency module.

Base currency is UZS. Exchange rates are stored as: 1 unit of currency = rate_to_base UZS.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import Currency, ExchangeRate, User
from services.audit import log_action
from services.permissions import user_has_permission

router = APIRouter(prefix="/currencies", tags=["currencies"])

SUPPORTED_CODES = {"UZS", "KZT", "USD", "RUB"}


def _can_manage(db: Session, user: User) -> bool:
    return user.role == "admin" or user_has_permission(db, user, "finance")


class RateIn(BaseModel):
    currency_code: str
    rate_to_base: float = Field(gt=0)
    rate_date: datetime | None = None


def serialize_currency(currency: Currency, latest_rate: ExchangeRate | None = None) -> dict:
    return {
        "id": currency.id,
        "code": currency.code,
        "name": currency.name,
        "symbol": currency.symbol,
        "is_base": bool(currency.is_base),
        "is_active": bool(currency.is_active),
        "rate_to_base": 1.0 if currency.is_base else (latest_rate.rate_to_base if latest_rate else None),
        "rate_date": (
            latest_rate.rate_date.isoformat()
            if latest_rate and latest_rate.rate_date
            else None
        ),
    }


def latest_rate_for(db: Session, code: str) -> ExchangeRate | None:
    return (
        db.query(ExchangeRate)
        .filter(ExchangeRate.currency_code == code)
        .order_by(desc(ExchangeRate.rate_date), desc(ExchangeRate.id))
        .first()
    )


def rate_to_base(db: Session, code: str) -> float | None:
    """UZS per 1 unit of `code`. Returns None when no rate is recorded."""
    code = (code or "UZS").upper()
    if code == "UZS":
        return 1.0
    rate = latest_rate_for(db, code)
    return rate.rate_to_base if rate else None


def convert_amount(db: Session, amount: float, from_code: str, to_code: str) -> float | None:
    src = rate_to_base(db, from_code)
    dst = rate_to_base(db, to_code)
    if src is None or dst is None or dst == 0:
        return None
    return amount * src / dst


@router.get("/")
def list_currencies(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    currencies = (
        db.query(Currency)
        .filter(Currency.is_active.is_(True))
        .order_by(Currency.sort_order)
        .all()
    )
    return {
        "base": "UZS",
        "currencies": [serialize_currency(c, latest_rate_for(db, c.code)) for c in currencies],
    }


@router.get("/rates/history")
def rate_history(
    currency_code: str = Query(...),
    limit: int = Query(default=60, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    code = currency_code.upper()
    rows = (
        db.query(ExchangeRate)
        .filter(ExchangeRate.currency_code == code)
        .order_by(desc(ExchangeRate.rate_date), desc(ExchangeRate.id))
        .limit(limit)
        .all()
    )
    return {
        "currency_code": code,
        "history": [
            {
                "id": r.id,
                "rate_to_base": r.rate_to_base,
                "rate_date": r.rate_date.isoformat() if r.rate_date else None,
                "created_by": r.created_by,
            }
            for r in rows
        ],
    }


@router.post("/rates")
def add_rate(
    payload: RateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_manage(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    code = payload.currency_code.upper()
    if code not in SUPPORTED_CODES:
        raise HTTPException(status_code=400, detail=f"Unsupported currency: {code}")
    if code == "UZS":
        raise HTTPException(status_code=400, detail="UZS is the base currency")
    rate = ExchangeRate(
        currency_code=code,
        rate_to_base=payload.rate_to_base,
        rate_date=payload.rate_date or datetime.utcnow(),
        created_by=user.username,
    )
    db.add(rate)
    db.commit()
    db.refresh(rate)
    log_action(db, user.username, "currency_rate_add", f"{code}={payload.rate_to_base}")
    return {
        "id": rate.id,
        "currency_code": rate.currency_code,
        "rate_to_base": rate.rate_to_base,
        "rate_date": rate.rate_date.isoformat() if rate.rate_date else None,
    }


@router.get("/convert")
def convert(
    amount: float = Query(...),
    from_code: str = Query(alias="from"),
    to_code: str = Query(alias="to"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = convert_amount(db, amount, from_code, to_code)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail="Exchange rate missing for requested currency pair",
        )
    return {
        "amount": amount,
        "from": from_code.upper(),
        "to": to_code.upper(),
        "converted": round(result, 4),
    }


@router.get("/dashboard")
def currency_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Latest rate per non-base currency for the dashboard widget."""
    currencies = (
        db.query(Currency)
        .filter(Currency.is_active.is_(True), Currency.is_base.is_(False))
        .order_by(Currency.sort_order)
        .all()
    )
    rates = []
    for c in currencies:
        latest = latest_rate_for(db, c.code)
        previous = None
        if latest:
            previous = (
                db.query(ExchangeRate)
                .filter(
                    ExchangeRate.currency_code == c.code,
                    ExchangeRate.id != latest.id,
                )
                .order_by(desc(ExchangeRate.rate_date), desc(ExchangeRate.id))
                .first()
            )
        rates.append(
            {
                "code": c.code,
                "symbol": c.symbol,
                "rate_to_base": latest.rate_to_base if latest else None,
                "previous_rate": previous.rate_to_base if previous else None,
                "rate_date": (
                    latest.rate_date.isoformat() if latest and latest.rate_date else None
                ),
            }
        )
    return {"base": "UZS", "rates": rates}
