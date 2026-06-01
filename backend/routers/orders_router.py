from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from auth.deps import get_current_user, require_admin
from constants import FIRST_STAGE, INSPECTION_STAGE, user_can_access_stage
from database import get_db
from models import Income, Order, OrderHistory, OrderImage, User
from schemas import (
    CompleteStageRequest,
    OrderCreate,
    OrderResponse,
    OrderUpdate,
    VerifyOrderRequest,
)
from services.notifications import notify_event
from services.telegram import format_new_order_alert, format_ready_order_alert
from services.workflow import add_history, complete_stage, verify_and_finish

router = APIRouter(prefix="/orders", tags=["orders"])


def _serialize_order(order: Order) -> dict:
    return OrderResponse(
        id=order.id,
        client=order.client,
        phone=order.phone or "",
        amount=order.amount or "0",
        comment=order.comment or "",
        destination=order.destination or "",
        status=order.status,
        operator_id=order.operator_id,
        image_url=order.image_url,
        images=order.images or [],
        history=sorted(order.history or [], key=lambda h: h.completed_at or datetime.min),
        in_warehouse=bool(order.in_warehouse),
        created_at=order.created_at,
        updated_at=order.updated_at,
        estimated_finish_at=order.estimated_finish_at,
    ).model_dump()


@router.get("")
def list_orders(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Order).options(
        joinedload(Order.history),
        joinedload(Order.images),
    ).filter(Order.in_warehouse.is_(False), Order.deleted_at.is_(None))

    if user.role != "admin" and user.department != "Admin":
        if user.department == "Ombor":
            query = query.filter(Order.status == "Tayyor")
        else:
            query = query.filter(Order.status == user.department)

    orders = query.order_by(Order.id.desc()).all()
    return [_serialize_order(o) for o in orders]


@router.get("/kanban")
def kanban_board(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Order).filter(
        Order.in_warehouse.is_(False),
        Order.deleted_at.is_(None),
        Order.status != "Tayyor",
    )
    if user.role != "admin" and user.department != "Admin":
        if user.department != "Ombor":
            query = query.filter(Order.status == user.department)

    orders = query.order_by(Order.updated_at.desc()).all()
    from constants import PRODUCTION_STAGES

    board = {stage: [] for stage in PRODUCTION_STAGES if stage != "Tayyor"}
    for order in orders:
        if order.status in board:
            board[order.status].append(_serialize_order(order))
    return board


@router.get("/{order_id}")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = (
        db.query(Order)
        .options(joinedload(Order.history), joinedload(Order.images))
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    dept = user.department or "Admin"
    if not user_can_access_stage(dept, user.role, order.status) and not order.in_warehouse:
        if user.department != "Ombor":
            raise HTTPException(status_code=403, detail="Access denied")

    return _serialize_order(order)


@router.post("")
async def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = Order(
        client=data.client,
        phone=data.phone,
        amount=data.amount,
        comment=data.comment,
        destination=data.destination,
        status=FIRST_STAGE,
        operator_id=user.id,
        image_url=data.image_url,
        estimated_finish_at=data.estimated_finish_at,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(order)
    db.flush()

    urls = list(data.image_urls or [])
    if data.image_url and data.image_url not in urls:
        urls.insert(0, data.image_url)
    for url in urls:
        db.add(OrderImage(order_id=order.id, url=url))

    add_history(db, order.id, FIRST_STAGE, user.username, "created", "Zakaz yaratildi — Kesish")
    db.add(
        Income(
            title=f"Zakaz #{order.id} - {order.client}",
            amount=float(order.amount or 0),
            source="order",
        )
    )
    db.commit()
    db.refresh(order)

    await notify_event(db, "new_order", format_new_order_alert(order))

    order = (
        db.query(Order)
        .options(joinedload(Order.history), joinedload(Order.images))
        .filter(Order.id == order.id)
        .first()
    )
    return _serialize_order(order)


@router.put("/{order_id}")
def update_order(
    order_id: int,
    data: OrderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    for field in ("client", "phone", "amount", "comment", "destination", "estimated_finish_at"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(order, field, val)
    order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(order)
    return _serialize_order(order)


@router.post("/{order_id}/complete")
async def complete_order_stage(
    order_id: int,
    body: CompleteStageRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    dept = user.department or user.role
    if not user_can_access_stage(dept, user.role, order.status):
        raise HTTPException(status_code=403, detail="Wrong department for this order")

    if order.status == INSPECTION_STAGE:
        raise HTTPException(
            status_code=400,
            detail="Use Tekshirildi button for Tekshiruv stage",
        )

    _, new_stage, moved_to_wh = complete_stage(db, order, user.username, body.comment)
    db.commit()

    if moved_to_wh:
        await notify_event(db, "order_completed", format_ready_order_alert(order))

    order = (
        db.query(Order)
        .options(joinedload(Order.history), joinedload(Order.images))
        .filter(Order.id == order_id)
        .first()
    )
    return _serialize_order(order)


@router.post("/{order_id}/verify")
async def verify_order(
    order_id: int,
    body: VerifyOrderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != INSPECTION_STAGE:
        raise HTTPException(status_code=400, detail="Order not in Tekshiruv")

    dept = user.department or ""
    if user.role != "admin" and dept not in ("Tekshiruv", "Admin"):
        raise HTTPException(status_code=403, detail="Only Tekshiruv can verify")

    try:
        verify_and_finish(db, order, user.username, body.comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    db.commit()
    await notify_event(db, "order_completed", format_ready_order_alert(order))

    order = (
        db.query(Order)
        .options(joinedload(Order.history), joinedload(Order.images))
        .filter(Order.id == order_id)
        .first()
    )
    return _serialize_order(order)


@router.get("/{order_id}/history")
def order_history(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    logs = (
        db.query(OrderHistory)
        .filter(OrderHistory.order_id == order_id)
        .order_by(OrderHistory.completed_at.asc())
        .all()
    )
    return logs


@router.delete("/{order_id}")
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    db.query(OrderHistory).filter(OrderHistory.order_id == order_id).delete()
    db.query(OrderImage).filter(OrderImage.order_id == order_id).delete()
    db.delete(order)
    db.commit()
    return {"message": "Deleted"}
