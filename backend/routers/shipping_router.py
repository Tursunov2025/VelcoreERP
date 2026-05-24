from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from auth.deps import get_current_user, require_admin
from database import get_db
from models import Order, ShipmentGroup, ShipmentItem, User, WarehouseItem
from pydantic import BaseModel
from services.audit import log_action

router = APIRouter(prefix="/shipping", tags=["shipping"])


class DispatchRequest(BaseModel):
    warehouse_item_ids: list[int]
    destination: str = ""
    comment: str = ""
    responsible_operator: str = ""


def _serialize_group(group: ShipmentGroup) -> dict:
    return {
        "id": group.id,
        "destination": group.destination or "",
        "comment": group.comment or "",
        "shipped_at": group.shipped_at,
        "warehouse_operator": group.warehouse_operator,
        "responsible_operator": group.responsible_operator or "",
        "total_products_count": group.total_products_count,
        "deleted_at": group.deleted_at,
        "items": [
            {
                "id": i.id,
                "order_id": i.order_id,
                "client": i.client,
                "phone": i.phone,
                "amount": i.amount,
                "product_destination": i.product_destination,
                "quantity": i.quantity,
            }
            for i in (group.items or [])
        ],
    }


def _check_ombor(user: User):
    if user.role == "admin" or user.department in ("Ombor", "Admin"):
        return
    raise HTTPException(status_code=403, detail="Ombor access required")


@router.post("/dispatch")
def dispatch_grouped_shipment(
    data: DispatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _check_ombor(user)
    if not data.warehouse_item_ids:
        raise HTTPException(status_code=400, detail="Mahsulot tanlang")

    now = datetime.utcnow()
    group = ShipmentGroup(
        destination=data.destination,
        comment=data.comment or "Yuk chiqarildi",
        shipped_at=now,
        warehouse_operator=user.username,
        responsible_operator=data.responsible_operator or user.username,
        total_products_count=0,
    )
    db.add(group)
    db.flush()

    count = 0
    for item_id in data.warehouse_item_ids:
        item = db.query(WarehouseItem).filter(WarehouseItem.id == item_id).first()
        if not item:
            continue

        db.add(
            ShipmentItem(
                shipment_group_id=group.id,
                order_id=item.order_id,
                client=item.client,
                phone=item.phone or "",
                amount=item.amount or "0",
                product_destination=item.destination or "",
                quantity=item.quantity or 1,
            )
        )
        count += 1

        order = db.query(Order).filter(Order.id == item.order_id).first()
        if order:
            order.in_warehouse = False
        db.delete(item)

    group.total_products_count = count
    log_action(
        db,
        user.username,
        "ship",
        "shipment_group",
        group.id,
        f"Shipment #{group.id} — {count} products",
    )
    db.commit()

    group = (
        db.query(ShipmentGroup)
        .options(joinedload(ShipmentGroup.items))
        .filter(ShipmentGroup.id == group.id)
        .first()
    )
    return {
        "message": "Yuk chiqarildi",
        "shipment": _serialize_group(group),
    }


@router.get("/groups")
def list_shipment_groups(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    q: str = Query(""),
    shipment_id: Optional[int] = Query(None),
    operator: str = Query(""),
    destination: str = Query(""),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    product: str = Query(""),
    include_deleted: bool = Query(False),
):
    _check_ombor(user)

    query = db.query(ShipmentGroup).options(joinedload(ShipmentGroup.items))

    if include_deleted and (user.role == "admin" or user.department == "Admin"):
        pass
    elif include_deleted:
        query = query.filter(ShipmentGroup.deleted_at.isnot(None))
    else:
        query = query.filter(ShipmentGroup.deleted_at.is_(None))

    if shipment_id:
        query = query.filter(ShipmentGroup.id == shipment_id)
    if destination.strip():
        query = query.filter(ShipmentGroup.destination.ilike(f"%{destination}%"))
    if operator.strip():
        op = operator.lower()
        query = query.filter(
            (ShipmentGroup.warehouse_operator.ilike(f"%{op}%"))
            | (ShipmentGroup.responsible_operator.ilike(f"%{op}%"))
        )
    if date_from:
        try:
            query = query.filter(
                ShipmentGroup.shipped_at >= datetime.fromisoformat(date_from)
            )
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(
                ShipmentGroup.shipped_at <= datetime.fromisoformat(date_to)
            )
        except ValueError:
            pass

    groups = query.order_by(ShipmentGroup.shipped_at.desc()).limit(300).all()

    if q.strip() or product.strip():
        search = (q or product).lower()
        filtered = []
        for g in groups:
            if search in str(g.id) or search in (g.destination or "").lower():
                filtered.append(g)
                continue
            if any(search in (i.client or "").lower() for i in g.items):
                filtered.append(g)
        groups = filtered

    return [_serialize_group(g) for g in groups]


@router.get("/groups/{group_id}")
def get_shipment_group(
    group_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _check_ombor(user)
    group = (
        db.query(ShipmentGroup)
        .options(joinedload(ShipmentGroup.items))
        .filter(ShipmentGroup.id == group_id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return _serialize_group(group)


@router.delete("/groups/{group_id}")
def admin_delete_shipment_group(
    group_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    group = db.query(ShipmentGroup).filter(ShipmentGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Shipment not found")
    group.deleted_at = datetime.utcnow()
    log_action(db, admin.username, "delete", "shipment_group", group_id)
    db.commit()
    return {"message": "Shipment archived (soft deleted)"}


@router.post("/groups/{group_id}/restore")
def admin_restore_shipment_group(
    group_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    group = db.query(ShipmentGroup).filter(ShipmentGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Shipment not found")
    group.deleted_at = None
    log_action(db, admin.username, "restore", "shipment_group", group_id)
    db.commit()
    return {"message": "Shipment restored"}


# Legacy endpoint
@router.get("/archive")
def legacy_archive(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    q: str = Query(""),
):
    return list_shipment_groups(db=db, user=user, q=q)
