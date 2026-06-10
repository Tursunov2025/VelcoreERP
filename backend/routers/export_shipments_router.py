from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from auth.deps import get_current_user
from database import get_db
from models import ExportShipment, ExportShipmentDocument, ExportShipmentItem, Order, User
from services.audit import log_action
from services.export_documents import (
    DOCUMENT_TYPES,
    audit_payload,
    generate_documents,
    recompute_totals,
    serialize_shipment,
)
from services.permissions import user_has_permission

router = APIRouter(prefix="/export-shipments", tags=["export-shipments"])

EXPORT_STATUSES = {"Draft", "Ready", "Sent", "Delivered"}


class ExportShipmentItemIn(BaseModel):
    product_name: str
    description: str = ""
    quantity: float = 1
    unit: str = "pcs"
    weight_kg: float = 0
    unit_price: float = 0
    total_amount: float | None = None


class ExportShipmentCreate(BaseModel):
    customer: str
    country: str = "Kazakhstan"
    contract_number: str = ""
    currency: str = "KZT"
    shipment_date: datetime | None = None
    notes: str = ""
    items: list[ExportShipmentItemIn] = Field(default_factory=list)


class ExportShipmentFromOrder(BaseModel):
    order_id: int
    country: str = "Kazakhstan"
    contract_number: str = ""
    currency: str = "KZT"
    shipment_date: datetime | None = None


class ExportShipmentUpdate(BaseModel):
    customer: str | None = None
    country: str | None = None
    contract_number: str | None = None
    currency: str | None = None
    shipment_date: datetime | None = None
    notes: str | None = None
    items: list[ExportShipmentItemIn] | None = None


class ExportStatusUpdate(BaseModel):
    status: Literal["Draft", "Ready", "Sent", "Delivered"]


def _can_view(db: Session, user: User) -> bool:
    return user_has_permission(db, user, "export_view") or user_has_permission(db, user, "llp_view")


def _can_manage(db: Session, user: User) -> bool:
    return user_has_permission(db, user, "export_manage") or user_has_permission(db, user, "llp_upload")


def _require_view(db: Session, user: User) -> None:
    if not _can_view(db, user):
        raise HTTPException(status_code=403, detail="Permission required: export_view")


def _require_manage(db: Session, user: User) -> None:
    if not _can_manage(db, user):
        raise HTTPException(status_code=403, detail="Permission required: export_manage")


def _parse_amount(value: str | None) -> float:
    if not value:
        return 0.0
    cleaned = "".join(ch for ch in str(value) if ch.isdigit() or ch in ".-")
    try:
        return float(cleaned or 0)
    except ValueError:
        return 0.0


def _next_shipment_number(db: Session) -> str:
    prefix = f"EXP-{datetime.utcnow():%Y%m%d}"
    count = db.query(ExportShipment).filter(ExportShipment.shipment_number.like(f"{prefix}-%")).count()
    return f"{prefix}-{count + 1:04d}"


def _with_relations(db: Session, shipment_id: int) -> ExportShipment | None:
    return (
        db.query(ExportShipment)
        .options(selectinload(ExportShipment.items), selectinload(ExportShipment.documents))
        .filter(ExportShipment.id == shipment_id)
        .first()
    )


def _replace_items(db: Session, shipment: ExportShipment, items: list[ExportShipmentItemIn]) -> None:
    db.query(ExportShipmentItem).filter(ExportShipmentItem.shipment_id == shipment.id).delete()
    for idx, item in enumerate(items):
        total = item.total_amount
        if total is None:
            total = float(item.quantity or 0) * float(item.unit_price or 0)
        db.add(
            ExportShipmentItem(
                shipment_id=shipment.id,
                order_id=shipment.order_id,
                product_name=item.product_name.strip(),
                description=item.description or "",
                quantity=item.quantity,
                unit=item.unit or "pcs",
                weight_kg=item.weight_kg,
                unit_price=item.unit_price,
                total_amount=total,
                sort_order=idx + 1,
            )
        )
    db.flush()
    db.refresh(shipment)
    recompute_totals(shipment)


@router.get("")
def list_export_shipments(
    status: str = "",
    q: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    query = db.query(ExportShipment).options(
        selectinload(ExportShipment.items), selectinload(ExportShipment.documents)
    )
    if status:
        query = query.filter(ExportShipment.status == status)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            ExportShipment.shipment_number.ilike(term)
            | ExportShipment.customer.ilike(term)
            | ExportShipment.contract_number.ilike(term)
        )
    rows = query.order_by(ExportShipment.created_at.desc()).all()
    return {"shipments": [serialize_shipment(row) for row in rows]}


@router.get("/dashboard")
def export_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    rows = db.query(ExportShipment.status, ExportShipment.id).all()
    by_status = {status: 0 for status in sorted(EXPORT_STATUSES)}
    for status, _ in rows:
        by_status[status or "Draft"] = by_status.get(status or "Draft", 0) + 1
    ready = by_status.get("Ready", 0)
    sent = by_status.get("Sent", 0)
    return {
        "total": len(rows),
        "ready": ready,
        "sent": sent,
        "delivered": by_status.get("Delivered", 0),
        "draft": by_status.get("Draft", 0),
        "by_status": by_status,
    }


@router.get("/{shipment_id}")
def get_export_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    shipment = _with_relations(db, shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Export shipment not found")
    return serialize_shipment(shipment)


@router.post("")
def create_export_shipment(
    data: ExportShipmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)
    if not data.customer.strip():
        raise HTTPException(status_code=400, detail="Customer is required")
    if not data.items:
        raise HTTPException(status_code=400, detail="At least one product is required")
    shipment = ExportShipment(
        shipment_number=_next_shipment_number(db),
        customer=data.customer.strip(),
        country=data.country or "Kazakhstan",
        contract_number=data.contract_number or "",
        currency=(data.currency or "KZT").upper(),
        shipment_date=data.shipment_date or datetime.utcnow(),
        notes=data.notes or "",
        created_by=user.username,
    )
    db.add(shipment)
    db.flush()
    _replace_items(db, shipment, data.items)
    log_action(db, user.username, "create", "export_shipment", shipment.id, audit_payload(shipment))
    db.commit()
    return serialize_shipment(_with_relations(db, shipment.id))


@router.post("/from-order")
def create_export_shipment_from_order(
    data: ExportShipmentFromOrder,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)
    order = db.query(Order).filter(Order.id == data.order_id, Order.deleted_at.is_(None)).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    amount = _parse_amount(order.amount)
    shipment = ExportShipment(
        shipment_number=_next_shipment_number(db),
        order_id=order.id,
        customer=order.client,
        country=data.country or order.destination or "Kazakhstan",
        contract_number=data.contract_number or "",
        currency=(data.currency or "KZT").upper(),
        shipment_date=data.shipment_date or datetime.utcnow(),
        notes=order.comment or "",
        created_by=user.username,
    )
    db.add(shipment)
    db.flush()
    db.add(
        ExportShipmentItem(
            shipment_id=shipment.id,
            order_id=order.id,
            product_name=f"Order #{order.id}",
            description=order.comment or order.destination or "",
            quantity=1,
            unit="pcs",
            weight_kg=0,
            unit_price=amount,
            total_amount=amount,
            sort_order=1,
        )
    )
    db.flush()
    db.refresh(shipment)
    recompute_totals(shipment)
    log_action(db, user.username, "create_from_order", "export_shipment", shipment.id, audit_payload(shipment))
    db.commit()
    return serialize_shipment(_with_relations(db, shipment.id))


@router.put("/{shipment_id}")
def update_export_shipment(
    shipment_id: int,
    data: ExportShipmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)
    shipment = _with_relations(db, shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Export shipment not found")
    for field in ("customer", "country", "contract_number", "currency", "shipment_date", "notes"):
        value = getattr(data, field)
        if value is not None:
            setattr(shipment, field, value.upper() if field == "currency" else value)
    if data.items is not None:
        _replace_items(db, shipment, data.items)
    shipment.updated_at = datetime.utcnow()
    log_action(db, user.username, "update", "export_shipment", shipment.id, audit_payload(shipment))
    db.commit()
    return serialize_shipment(_with_relations(db, shipment.id))


@router.post("/{shipment_id}/status")
def update_export_status(
    shipment_id: int,
    data: ExportStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)
    shipment = _with_relations(db, shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Export shipment not found")
    shipment.status = data.status
    shipment.updated_at = datetime.utcnow()
    if data.status == "Sent":
        shipment.sent_at = shipment.sent_at or datetime.utcnow()
    if data.status == "Delivered":
        shipment.delivered_at = shipment.delivered_at or datetime.utcnow()
    log_action(db, user.username, "status", "export_shipment", shipment.id, audit_payload(shipment))
    db.commit()
    return serialize_shipment(_with_relations(db, shipment.id))


@router.post("/{shipment_id}/generate-documents")
def generate_export_documents(
    shipment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)
    shipment = _with_relations(db, shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Export shipment not found")
    if not shipment.items:
        raise HTTPException(status_code=400, detail="Shipment has no products")
    generate_documents(db, shipment, user.username)
    shipment.status = "Ready"
    shipment.updated_at = datetime.utcnow()
    log_action(db, user.username, "generate_documents", "export_shipment", shipment.id, audit_payload(shipment))
    db.commit()
    return serialize_shipment(_with_relations(db, shipment.id))


@router.get("/documents/{document_id}/download")
def download_export_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    doc = db.query(ExportShipmentDocument).filter(ExportShipmentDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.document_type not in DOCUMENT_TYPES and not doc.document_type.endswith("_xlsx"):
        raise HTTPException(status_code=400, detail="Invalid document type")
    # Resolve from configured upload root by URL suffix to keep Windows and Render paths portable.
    from routers.uploads_router import UPLOAD_DIR

    rel_parts = [part for part in doc.url.replace("/uploads/", "").split("/") if part]
    path = UPLOAD_DIR.joinpath(*rel_parts)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Generated file missing")
    return FileResponse(path, media_type=doc.content_type, filename=doc.filename)

