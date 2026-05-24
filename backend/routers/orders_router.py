from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.deps import get_current_user, require_admin
from database import get_db
from models import Income, Order, ProductionLog, User
from schemas import OrderCreate, OrderResponse, OrderUpdate, PRODUCTION_STAGES
from services.telegram import (
    format_new_order_alert,
    format_ready_order_alert,
    send_telegram_message,
)

router = APIRouter(prefix="/orders", tags=["orders"])


def _log_stage(db: Session, order_id: int, stage: str, username: str, notes: str = ""):
    db.add(
        ProductionLog(
            order_id=order_id,
            stage=stage,
            changed_by=username,
            notes=notes,
        )
    )


@router.get("", response_model=list[OrderResponse])
def list_orders(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return db.query(Order).order_by(Order.id.desc()).all()


@router.post("", response_model=OrderResponse)
async def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = Order(
        client=data.client,
        phone=data.phone,
        amount=data.amount,
        status="Yangi",
        operator_id=user.id,
        image_url=data.image_url,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    _log_stage(db, order.id, "Yangi", user.username, "Zakaz yaratildi")
    db.add(
        Income(
            title=f"Zakaz #{order.id} - {order.client}",
            amount=float(order.amount or 0),
            source="order",
        )
    )
    db.commit()

    await send_telegram_message(format_new_order_alert(order))
    await send_telegram_message(
        f"📢 <b>Admin bildirishnoma</b>\nYangi zakaz operator: {user.username}"
    )

    return order


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: int,
    data: OrderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    old_status = order.status
    if data.client is not None:
        order.client = data.client
    if data.phone is not None:
        order.phone = data.phone
    if data.amount is not None:
        order.amount = data.amount
    if data.image_url is not None:
        order.image_url = data.image_url
    if data.status is not None:
        if data.status not in PRODUCTION_STAGES:
            raise HTTPException(status_code=400, detail="Invalid status")
        order.status = data.status

    order.updated_at = datetime.utcnow()

    if data.status and data.status != old_status:
        _log_stage(db, order.id, data.status, user.username)
        if data.status == "Tayyor":
            await send_telegram_message(format_ready_order_alert(order))

    db.commit()
    db.refresh(order)
    return order


@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_status(
    order_id: int,
    status: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await update_order(
        order_id,
        OrderUpdate(status=status),
        db,
        user,
    )


@router.delete("/{order_id}")
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    db.query(ProductionLog).filter(ProductionLog.order_id == order_id).delete()
    db.delete(order)
    db.commit()
    return {"message": "Deleted"}
