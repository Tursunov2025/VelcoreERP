"""Velcore ERP — Logistics module (finished warehouse, loading plans, scan control)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from auth.deps import get_current_user
from database import get_db
from models import (
    Driver,
    GpsLocation,
    LogisticsFinishedProduct,
    LogisticsLoadingShipment,
    LogisticsLoadingShipmentItem,
    Transport,
    User,
    Vehicle,
)
from services.audit import log_action
from services.gps_fleet import latest_location_for_vehicle, serialize_location
from services.permissions import user_has_permission

router = APIRouter(prefix="/logistics", tags=["logistics"])

PRODUCT_STATUSES = ("Available", "Reserved", "Loaded", "Delivered")
SHIPMENT_STATUSES = ("planned", "loading", "in_transit", "delivered", "cancelled")


def _can_view(db: Session, user: User) -> bool:
    return user.role == "admin" or user_has_permission(db, user, "export_view")


def _can_manage(db: Session, user: User) -> bool:
    return user.role == "admin" or user_has_permission(db, user, "export_manage")


def _require_view(db: Session, user: User) -> None:
    if not _can_view(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")


def _require_manage(db: Session, user: User) -> None:
    if not _can_manage(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")


def _next_shipment_no(db: Session) -> str:
    count = db.query(func.count(LogisticsLoadingShipment.id)).scalar() or 0
    return f"LD-{datetime.utcnow():%Y%m%d}-{count + 1:04d}"


def _serialize_product(p: LogisticsFinishedProduct) -> dict:
    return {
        "id": p.id,
        "product_code": p.product_code,
        "product_name": p.product_name,
        "order_number": p.order_number,
        "quantity": p.quantity,
        "warehouse_location": p.warehouse_location,
        "status": p.status,
        "vehicle_id": p.vehicle_id,
        "driver_id": p.driver_id,
        "vehicle": (
            {"id": p.vehicle.id, "plate_number": p.vehicle.plate_number, "model": p.vehicle.model}
            if p.vehicle
            else None
        ),
        "driver": (
            {"id": p.driver.id, "full_name": p.driver.full_name, "phone": p.driver.phone}
            if p.driver
            else None
        ),
        "barcode": p.barcode,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _serialize_shipment(
    s: LogisticsLoadingShipment,
    *,
    gps: dict | None = None,
    include_items: bool = False,
) -> dict:
    data = {
        "id": s.id,
        "shipment_no": s.shipment_no,
        "vehicle_id": s.vehicle_id,
        "driver_id": s.driver_id,
        "transport_id": s.transport_id,
        "destination": s.destination,
        "status": s.status,
        "created_by": s.created_by,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "departed_at": s.departed_at.isoformat() if s.departed_at else None,
        "delivered_at": s.delivered_at.isoformat() if s.delivered_at else None,
        "vehicle": (
            {"id": s.vehicle.id, "plate_number": s.vehicle.plate_number, "model": s.vehicle.model}
            if s.vehicle
            else None
        ),
        "driver": (
            {"id": s.driver.id, "full_name": s.driver.full_name, "phone": s.driver.phone}
            if s.driver
            else None
        ),
        "transport": (
            {"id": s.transport.id, "destination": s.transport.destination, "status": s.transport.status}
            if s.transport
            else None
        ),
        "gps_location": gps,
    }
    if include_items:
        data["items"] = [
            {
                "id": i.id,
                "product_id": i.product_id,
                "qty": i.qty,
                "loaded_at": i.loaded_at.isoformat() if i.loaded_at else None,
                "loaded_by": i.loaded_by,
                "product": _serialize_product(i.product) if i.product else None,
            }
            for i in (s.items or [])
        ]
    return data


class ProductIn(BaseModel):
    product_code: str
    product_name: str
    order_number: str = ""
    quantity: float = Field(default=1, gt=0)
    warehouse_location: str = ""
    status: Literal["Available", "Reserved", "Loaded", "Delivered"] = "Available"
    vehicle_id: int | None = None
    driver_id: int | None = None
    barcode: str | None = None


class ProductUpdate(BaseModel):
    product_code: str | None = None
    product_name: str | None = None
    order_number: str | None = None
    quantity: float | None = None
    warehouse_location: str | None = None
    status: Literal["Available", "Reserved", "Loaded", "Delivered"] | None = None
    vehicle_id: int | None = None
    driver_id: int | None = None


class ShipmentIn(BaseModel):
    vehicle_id: int | None = None
    driver_id: int | None = None
    transport_id: int | None = None
    destination: str = ""
    status: Literal["planned", "loading", "in_transit", "delivered", "cancelled"] = "planned"


class ShipmentItemIn(BaseModel):
    product_id: int
    qty: float = Field(default=1, gt=0)


class LoadingScanIn(BaseModel):
    barcode: str
    shipment_id: int
    vehicle_id: int | None = None
    driver_id: int | None = None
    qty: float = Field(default=1, gt=0)


@router.get("/dashboard")
def logistics_dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_view(db, user)
    products = db.query(LogisticsFinishedProduct)
    shipments = db.query(LogisticsLoadingShipment)
    return {
        "finished_products": {
            "total": products.count(),
            "available": products.filter(LogisticsFinishedProduct.status == "Available").count(),
            "reserved": products.filter(LogisticsFinishedProduct.status == "Reserved").count(),
            "loaded": products.filter(LogisticsFinishedProduct.status == "Loaded").count(),
            "delivered": products.filter(LogisticsFinishedProduct.status == "Delivered").count(),
            "ready": products.filter(LogisticsFinishedProduct.status == "Available").count(),
            "loading": products.filter(LogisticsFinishedProduct.status == "Reserved").count(),
        },
        "shipments": {
            "total": shipments.count(),
            "planned": shipments.filter(LogisticsLoadingShipment.status == "planned").count(),
            "loading": shipments.filter(LogisticsLoadingShipment.status == "loading").count(),
            "in_transit": shipments.filter(LogisticsLoadingShipment.status == "in_transit").count(),
            "delivered": shipments.filter(LogisticsLoadingShipment.status == "delivered").count(),
        },
    }


@router.get("/products")
def list_products(
    status: str = Query(""),
    q: str = Query(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    query = (
        db.query(LogisticsFinishedProduct)
        .options(
            joinedload(LogisticsFinishedProduct.vehicle),
            joinedload(LogisticsFinishedProduct.driver),
        )
        .order_by(desc(LogisticsFinishedProduct.updated_at))
    )
    if status:
        query = query.filter(LogisticsFinishedProduct.status == status)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            LogisticsFinishedProduct.product_code.ilike(term)
            | LogisticsFinishedProduct.product_name.ilike(term)
            | LogisticsFinishedProduct.order_number.ilike(term)
            | LogisticsFinishedProduct.barcode.ilike(term)
        )
    rows = query.limit(500).all()
    return {"products": [_serialize_product(p) for p in rows]}


@router.post("/products")
def create_product(
    payload: ProductIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)
    code = payload.product_code.strip()
    name = payload.product_name.strip()
    if not code or not name:
        raise HTTPException(status_code=400, detail="product_code and product_name required")
    barcode = (payload.barcode or "").strip() or f"PRD-{code}-{uuid.uuid4().hex[:8].upper()}"
    if db.query(LogisticsFinishedProduct).filter(LogisticsFinishedProduct.barcode == barcode).first():
        raise HTTPException(status_code=400, detail="barcode already exists")
    if payload.vehicle_id and not db.query(Vehicle).filter(Vehicle.id == payload.vehicle_id).first():
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if payload.driver_id and not db.query(Driver).filter(Driver.id == payload.driver_id).first():
        raise HTTPException(status_code=404, detail="Driver not found")
    product = LogisticsFinishedProduct(
        product_code=code,
        product_name=name,
        order_number=payload.order_number.strip(),
        quantity=payload.quantity,
        warehouse_location=payload.warehouse_location.strip(),
        status=payload.status,
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
        barcode=barcode,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    log_action(db, user.username, "logistics_product_create", f"product={product.id}")
    return _serialize_product(product)


@router.put("/products/{product_id}")
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)
    product = db.query(LogisticsFinishedProduct).filter(LogisticsFinishedProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field in ("product_code", "product_name", "order_number", "warehouse_location", "status"):
        val = getattr(payload, field)
        if val is not None:
            setattr(product, field, val.strip() if isinstance(val, str) else val)
    if payload.quantity is not None:
        product.quantity = payload.quantity
    if payload.vehicle_id is not None:
        if payload.vehicle_id and not db.query(Vehicle).filter(Vehicle.id == payload.vehicle_id).first():
            raise HTTPException(status_code=404, detail="Vehicle not found")
        product.vehicle_id = payload.vehicle_id or None
    if payload.driver_id is not None:
        if payload.driver_id and not db.query(Driver).filter(Driver.id == payload.driver_id).first():
            raise HTTPException(status_code=404, detail="Driver not found")
        product.driver_id = payload.driver_id or None
    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    return _serialize_product(product)


@router.get("/shipments")
def list_shipments(
    status: str = Query(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    query = (
        db.query(LogisticsLoadingShipment)
        .options(
            joinedload(LogisticsLoadingShipment.vehicle),
            joinedload(LogisticsLoadingShipment.driver),
            joinedload(LogisticsLoadingShipment.transport),
        )
        .order_by(desc(LogisticsLoadingShipment.created_at))
    )
    if status:
        query = query.filter(LogisticsLoadingShipment.status == status)
    rows = query.limit(200).all()
    result = []
    for s in rows:
        gps = None
        if s.vehicle_id:
            loc = latest_location_for_vehicle(db, s.vehicle_id)
            if loc:
                gps = serialize_location(loc)
        result.append(_serialize_shipment(s, gps=gps))
    return {"shipments": result}


@router.post("/shipments")
def create_shipment(
    payload: ShipmentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)
    shipment = LogisticsLoadingShipment(
        shipment_no=_next_shipment_no(db),
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
        transport_id=payload.transport_id,
        destination=payload.destination.strip(),
        status=payload.status,
        created_by=user.username,
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)
    log_action(db, user.username, "logistics_shipment_create", f"shipment={shipment.id}")
    return _serialize_shipment(shipment)


@router.get("/shipments/{shipment_id}")
def get_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    shipment = (
        db.query(LogisticsLoadingShipment)
        .options(
            joinedload(LogisticsLoadingShipment.vehicle),
            joinedload(LogisticsLoadingShipment.driver),
            joinedload(LogisticsLoadingShipment.transport),
            joinedload(LogisticsLoadingShipment.items).joinedload(LogisticsLoadingShipmentItem.product),
        )
        .filter(LogisticsLoadingShipment.id == shipment_id)
        .first()
    )
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    gps = None
    if shipment.vehicle_id:
        loc = latest_location_for_vehicle(db, shipment.vehicle_id)
        if loc:
            gps = serialize_location(loc)
    return _serialize_shipment(shipment, gps=gps, include_items=True)


@router.post("/shipments/{shipment_id}/items")
def add_shipment_item(
    shipment_id: int,
    payload: ShipmentItemIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)
    shipment = db.query(LogisticsLoadingShipment).filter(LogisticsLoadingShipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    product = db.query(LogisticsFinishedProduct).filter(LogisticsFinishedProduct.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.quantity < payload.qty:
        raise HTTPException(status_code=400, detail="Insufficient stock in warehouse")
    product.quantity -= payload.qty
    if product.quantity <= 0:
        product.quantity = 0
        product.status = "Loaded"
    else:
        product.status = "Reserved"
    if shipment.vehicle_id:
        product.vehicle_id = shipment.vehicle_id
    if shipment.driver_id:
        product.driver_id = shipment.driver_id
    product.updated_at = datetime.utcnow()
    item = LogisticsLoadingShipmentItem(
        shipment_id=shipment.id,
        product_id=product.id,
        qty=payload.qty,
        loaded_by=user.username,
    )
    db.add(item)
    if shipment.status == "planned":
        shipment.status = "loading"
    db.commit()
    return {"message": "Item added", "product": _serialize_product(product)}


@router.post("/loading/scan")
def loading_scan(
    payload: LoadingScanIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Barcode/QR scan: Product → Vehicle → Driver → Shipment."""
    _require_manage(db, user)
    code = payload.barcode.strip()
    if not code:
        raise HTTPException(status_code=400, detail="barcode required")
    shipment = db.query(LogisticsLoadingShipment).filter(LogisticsLoadingShipment.id == payload.shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    product = (
        db.query(LogisticsFinishedProduct)
        .filter(
            (LogisticsFinishedProduct.barcode == code)
            | (LogisticsFinishedProduct.product_code == code)
        )
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found for barcode")
    if product.status not in ("Available", "Reserved"):
        raise HTTPException(status_code=400, detail=f"Product status is {product.status}")

    if payload.vehicle_id:
        if not db.query(Vehicle).filter(Vehicle.id == payload.vehicle_id).first():
            raise HTTPException(status_code=404, detail="Vehicle not found")
        shipment.vehicle_id = payload.vehicle_id
    if payload.driver_id:
        if not db.query(Driver).filter(Driver.id == payload.driver_id).first():
            raise HTTPException(status_code=404, detail="Driver not found")
        shipment.driver_id = payload.driver_id

    qty = min(payload.qty, product.quantity)
    if qty <= 0:
        raise HTTPException(status_code=400, detail="No quantity available")

    product.quantity -= qty
    if product.quantity <= 0:
        product.quantity = 0
        product.status = "Loaded"
    else:
        product.status = "Reserved"
    if shipment.vehicle_id:
        product.vehicle_id = shipment.vehicle_id
    if shipment.driver_id:
        product.driver_id = shipment.driver_id
    product.updated_at = datetime.utcnow()

    db.add(
        LogisticsLoadingShipmentItem(
            shipment_id=shipment.id,
            product_id=product.id,
            qty=qty,
            loaded_by=user.username,
        )
    )
    if shipment.status == "planned":
        shipment.status = "loading"
    shipment.updated_at = datetime.utcnow()
    db.commit()
    log_action(
        db,
        user.username,
        "logistics_loading_scan",
        f"shipment={shipment.id} product={product.id} qty={qty}",
    )
    return {
        "message": "Scanned successfully",
        "shipment_id": shipment.id,
        "vehicle_id": shipment.vehicle_id,
        "driver_id": shipment.driver_id,
        "product": _serialize_product(product),
    }


@router.post("/shipments/{shipment_id}/depart")
def depart_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)
    shipment = db.query(LogisticsLoadingShipment).filter(LogisticsLoadingShipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    shipment.status = "in_transit"
    shipment.departed_at = datetime.utcnow()
    db.commit()
    return {"message": "Shipment departed", "status": shipment.status}


@router.post("/shipments/{shipment_id}/deliver")
def deliver_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)
    shipment = (
        db.query(LogisticsLoadingShipment)
        .options(joinedload(LogisticsLoadingShipment.items).joinedload(LogisticsLoadingShipmentItem.product))
        .filter(LogisticsLoadingShipment.id == shipment_id)
        .first()
    )
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    shipment.status = "delivered"
    shipment.delivered_at = datetime.utcnow()
    for item in shipment.items or []:
        if item.product:
            item.product.status = "Delivered"
            item.product.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Shipment delivered", "status": shipment.status}
