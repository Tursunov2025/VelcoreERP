"""Phase 11B — Transport Management for export logistics."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session, selectinload

from auth.deps import get_current_user
from database import get_db
from models import ExportShipment, Transport, TransportEvent, User
from services.audit import log_action
from services.permissions import user_has_permission

router = APIRouter(prefix="/transports", tags=["transports"])

TRANSPORT_STATUSES = ["Draft", "Loaded", "In Transit", "Border", "Delivered"]


def _can_view(db: Session, user: User) -> bool:
    return user.role == "admin" or user_has_permission(db, user, "export_view")


def _can_manage(db: Session, user: User) -> bool:
    return user.role == "admin" or user_has_permission(db, user, "export_manage")


class TransportCreate(BaseModel):
    vehicle: str
    driver_name: str = ""
    driver_phone: str = ""
    shipment_weight_kg: float = 0
    departure_date: datetime | None = None
    arrival_date: datetime | None = None
    export_shipment_id: int | None = None
    notes: str = ""


class TransportUpdate(BaseModel):
    vehicle: str | None = None
    driver_name: str | None = None
    driver_phone: str | None = None
    shipment_weight_kg: float | None = None
    departure_date: datetime | None = None
    arrival_date: datetime | None = None
    export_shipment_id: int | None = None
    notes: str | None = None


class TransportStatusUpdate(BaseModel):
    status: Literal["Draft", "Loaded", "In Transit", "Border", "Delivered"]
    comment: str = ""


def serialize_transport(transport: Transport, with_events: bool = False) -> dict:
    data = {
        "id": transport.id,
        "vehicle": transport.vehicle,
        "driver_name": transport.driver_name,
        "driver_phone": transport.driver_phone,
        "shipment_weight_kg": transport.shipment_weight_kg,
        "departure_date": (
            transport.departure_date.isoformat() if transport.departure_date else None
        ),
        "arrival_date": transport.arrival_date.isoformat() if transport.arrival_date else None,
        "status": transport.status,
        "notes": transport.notes,
        "export_shipment_id": transport.export_shipment_id,
        "export_shipment_number": (
            transport.export_shipment.shipment_number if transport.export_shipment else None
        ),
        "export_customer": (
            transport.export_shipment.customer if transport.export_shipment else None
        ),
        "created_by": transport.created_by,
        "created_at": transport.created_at.isoformat() if transport.created_at else None,
    }
    if with_events:
        data["events"] = [
            {
                "id": e.id,
                "status": e.status,
                "comment": e.comment,
                "created_by": e.created_by,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in sorted(transport.events, key=lambda e: (e.created_at or datetime.min, e.id))
        ]
    return data


def _get_transport(db: Session, transport_id: int) -> Transport:
    transport = (
        db.query(Transport)
        .options(selectinload(Transport.events), selectinload(Transport.export_shipment))
        .filter(Transport.id == transport_id)
        .first()
    )
    if not transport:
        raise HTTPException(status_code=404, detail="Transport not found")
    return transport


@router.get("/")
def list_transports(
    status: str = Query(default=""),
    q: str = Query(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_view(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    query = db.query(Transport).options(
        selectinload(Transport.events), selectinload(Transport.export_shipment)
    )
    if status:
        query = query.filter(Transport.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Transport.vehicle.ilike(like))
            | (Transport.driver_name.ilike(like))
            | (Transport.driver_phone.ilike(like))
        )
    transports = query.order_by(desc(Transport.created_at)).limit(300).all()
    return {
        "statuses": TRANSPORT_STATUSES,
        "transports": [serialize_transport(t, with_events=True) for t in transports],
    }


@router.get("/dashboard")
def transport_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_view(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    counts = {status: 0 for status in TRANSPORT_STATUSES}
    for transport in db.query(Transport).all():
        counts[transport.status] = counts.get(transport.status, 0) + 1
    return {"total": sum(counts.values()), "by_status": counts}


@router.get("/{transport_id}")
def get_transport(
    transport_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_view(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    return serialize_transport(_get_transport(db, transport_id), with_events=True)


@router.post("/")
def create_transport(
    payload: TransportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_manage(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    if payload.export_shipment_id is not None:
        shipment = (
            db.query(ExportShipment)
            .filter(ExportShipment.id == payload.export_shipment_id)
            .first()
        )
        if not shipment:
            raise HTTPException(status_code=404, detail="Export shipment not found")
    transport = Transport(
        vehicle=payload.vehicle.strip(),
        driver_name=payload.driver_name.strip(),
        driver_phone=payload.driver_phone.strip(),
        shipment_weight_kg=payload.shipment_weight_kg,
        departure_date=payload.departure_date,
        arrival_date=payload.arrival_date,
        export_shipment_id=payload.export_shipment_id,
        notes=payload.notes,
        status="Draft",
        created_by=user.username,
    )
    db.add(transport)
    db.flush()
    db.add(
        TransportEvent(
            transport_id=transport.id,
            status="Draft",
            comment="Transport created",
            created_by=user.username,
        )
    )
    db.commit()
    log_action(db, user.username, "transport_create", f"transport={transport.id}")
    return serialize_transport(_get_transport(db, transport.id), with_events=True)


@router.put("/{transport_id}")
def update_transport(
    transport_id: int,
    payload: TransportUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_manage(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    transport = _get_transport(db, transport_id)
    data = payload.model_dump(exclude_unset=True)
    if "export_shipment_id" in data and data["export_shipment_id"] is not None:
        shipment = (
            db.query(ExportShipment)
            .filter(ExportShipment.id == data["export_shipment_id"])
            .first()
        )
        if not shipment:
            raise HTTPException(status_code=404, detail="Export shipment not found")
    for field, value in data.items():
        setattr(transport, field, value)
    db.commit()
    log_action(db, user.username, "transport_update", f"transport={transport.id}")
    return serialize_transport(_get_transport(db, transport.id), with_events=True)


@router.post("/{transport_id}/status")
def update_transport_status(
    transport_id: int,
    payload: TransportStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_manage(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    transport = _get_transport(db, transport_id)
    transport.status = payload.status
    if payload.status == "Loaded" and not transport.departure_date:
        transport.departure_date = datetime.utcnow()
    if payload.status == "Delivered" and not transport.arrival_date:
        transport.arrival_date = datetime.utcnow()
    db.add(
        TransportEvent(
            transport_id=transport.id,
            status=payload.status,
            comment=payload.comment,
            created_by=user.username,
        )
    )
    db.commit()
    log_action(
        db, user.username, "transport_status", f"transport={transport.id} -> {payload.status}"
    )
    return serialize_transport(_get_transport(db, transport.id), with_events=True)
