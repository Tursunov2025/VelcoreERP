from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from constants import FINAL_STAGE, INSPECTION_STAGE, next_stage
from models import Order, OrderHistory, WarehouseItem


def add_history(
    db: Session,
    order_id: int,
    stage: str,
    operator_username: str,
    action: str,
    comment: str = "",
    started_at: Optional[datetime] = None,
):
    db.add(
        OrderHistory(
            order_id=order_id,
            stage=stage,
            operator_username=operator_username,
            action=action,
            comment=comment,
            started_at=started_at or datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
    )


def move_to_warehouse(db: Session, order: Order):
    existing = (
        db.query(WarehouseItem).filter(WarehouseItem.order_id == order.id).first()
    )
    if existing:
        order.in_warehouse = True
        return existing

    item = WarehouseItem(
        order_id=order.id,
        client=order.client,
        phone=order.phone,
        amount=order.amount,
        destination=order.destination or "",
        quantity=1,
        stored_at=datetime.utcnow(),
        comment=order.comment or "",
    )
    order.in_warehouse = True
    db.add(item)
    return item


def complete_stage(
    db: Session, order: Order, operator_username: str, comment: str = ""
) -> Tuple[Order, str, bool]:
    current = order.status
    add_history(
        db,
        order.id,
        current,
        operator_username,
        action="completed",
        comment=comment or f"{operator_username} tugatdi: {current}",
    )

    nxt = next_stage(current)
    if not nxt:
        order.status = FINAL_STAGE
        order.updated_at = datetime.utcnow()
        move_to_warehouse(db, order)
        return order, FINAL_STAGE, True

    order.status = nxt
    order.updated_at = datetime.utcnow()
    add_history(
        db,
        order.id,
        nxt,
        "system",
        action="received",
        comment=f"Buyurtma {nxt} bo'limiga o'tdi",
    )
    return order, nxt, False


def verify_and_finish(db: Session, order: Order, operator_username: str, comment: str = ""):
    if order.status != INSPECTION_STAGE:
        raise ValueError("Order is not in Tekshiruv stage")

    add_history(
        db,
        order.id,
        INSPECTION_STAGE,
        operator_username,
        action="verified",
        comment=comment or f"{operator_username} tekshirdi",
    )

    order.status = FINAL_STAGE
    order.updated_at = datetime.utcnow()
    add_history(
        db,
        order.id,
        FINAL_STAGE,
        operator_username,
        action="ready",
        comment="Buyurtma tayyor",
    )
    move_to_warehouse(db, order)
    return order
