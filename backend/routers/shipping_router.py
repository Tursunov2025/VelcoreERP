from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import Order, ShipmentArchive, User, WarehouseItem
from schemas import ShipmentArchiveResponse, ShipmentRequest

router = APIRouter(prefix="/shipping", tags=["shipping"])


@router.post("/dispatch")
def dispatch_shipment(
    data: ShipmentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin" and user.department not in ("Ombor", "Admin"):
        raise HTTPException(status_code=403, detail="Ombor access required")

    if not data.warehouse_item_ids:
        raise HTTPException(status_code=400, detail="Select products to ship")

    archived = []
    for item_id in data.warehouse_item_ids:
        item = db.query(WarehouseItem).filter(WarehouseItem.id == item_id).first()
        if not item:
            continue

        record = ShipmentArchive(
            order_id=item.order_id,
            client=item.client,
            destination=data.destination or item.destination,
            amount=item.amount,
            shipped_at=datetime.utcnow(),
            operator_username=user.username,
            comment=data.comment or "Yuk chiqarildi",
        )
        db.add(record)
        archived.append(record)

        order = db.query(Order).filter(Order.id == item.order_id).first()
        if order:
            db.delete(order)
        db.delete(item)

    db.commit()
    return {
        "message": "Yuk chiqarildi",
        "count": len(archived),
    }


@router.get("/archive", response_model=list[ShipmentArchiveResponse])
def shipping_archive(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin" and user.department not in ("Ombor", "Admin"):
        raise HTTPException(status_code=403, detail="Access denied")

    return (
        db.query(ShipmentArchive)
        .order_by(ShipmentArchive.shipped_at.desc())
        .limit(200)
        .all()
    )
