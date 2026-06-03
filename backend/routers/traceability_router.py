"""Package traceability, labels, scanner, and public tracking."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.deps import get_current_user, require_admin
from database import get_db
from models import User
from services.mes_dispatch_terminal import get_job_dispatch
from services.label_printer import get_printers_config, save_printers_config
from services.package_traceability import (
    assign_package_location,
    build_passport,
    build_public_tracking,
    scan_dispatch_load,
    traceability_dashboard,
)
from services.permissions import user_has_permission

router = APIRouter(tags=["traceability"])
public_router = APIRouter(tags=["traceability-public"])


class LocationAssignBody(BaseModel):
    warehouse_zone: str = ""
    rack: str = ""
    shelf: str = ""


class DispatchScanBody(BaseModel):
    label_code: str
    dispatch_id: int


class PrintersUpdateBody(BaseModel):
    printers: list[dict]


def _require_mes_view(db: Session, user: User) -> None:
    if user.role == "admin" or user_has_permission(db, user, "mes_view"):
        return
    raise HTTPException(status_code=403, detail="Permission required: mes_view")


@router.get("/traceability/dashboard")
def traceability_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_mes_view(db, user)
    return traceability_dashboard(db)


@router.get("/packages/{label_code}")
def package_passport(
    label_code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_mes_view(db, user)
    data = build_passport(db, label_code)
    if not data:
        raise HTTPException(status_code=404, detail="Package not found")
    return data


@public_router.get("/track/package/{label_code}")
def public_package_track(label_code: str, db: Session = Depends(get_db)):
    data = build_public_tracking(db, label_code)
    if not data:
        raise HTTPException(status_code=404, detail="Package not found")
    return data


@router.put("/packages/{label_code}/location")
def set_package_location(
    label_code: str,
    body: LocationAssignBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not (
        user.role == "admin"
        or user_has_permission(db, user, "mes_terminal_warehouse")
        or user_has_permission(db, user, "mes_edit")
    ):
        raise HTTPException(status_code=403, detail="Warehouse permission required")
    try:
        loc = assign_package_location(
            db,
            label_code=label_code,
            warehouse_zone=body.warehouse_zone,
            rack=body.rack,
            shelf=body.shelf,
            username=user.username,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "warehouse_zone": loc.warehouse_zone,
        "rack": loc.rack,
        "shelf": loc.shelf,
        "updated_at": loc.updated_at,
    }


@router.post("/mes/terminal/dispatch/scan-label")
def dispatch_scan_label(
    body: DispatchScanBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not (
        user.role == "admin"
        or user_has_permission(db, user, "mes_terminal_dispatch")
    ):
        raise HTTPException(status_code=403, detail="Dispatch terminal permission required")
    try:
        result = scan_dispatch_load(
            db,
            label_code=body.label_code,
            dispatch_id=body.dispatch_id,
            username=user.username,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


class DispatchScanJobBody(BaseModel):
    label_code: str


@router.post("/mes/terminal/dispatch/jobs/{job_id}/scan-label")
def dispatch_scan_label_for_job(
    job_id: int,
    body: DispatchScanJobBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not (
        user.role == "admin"
        or user_has_permission(db, user, "mes_terminal_dispatch")
    ):
        raise HTTPException(status_code=403, detail="Dispatch terminal permission required")
    dispatch = get_job_dispatch(db, job_id)
    if not dispatch:
        raise HTTPException(status_code=400, detail="Dispatch not started for this job")
    try:
        result = scan_dispatch_load(
            db,
            label_code=body.label_code,
            dispatch_id=dispatch.id,
            username=user.username,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.get("/admin/settings/label-printers")
def get_label_printers(
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
):
    return {"printers": get_printers_config(db)}


@router.put("/admin/settings/label-printers")
def put_label_printers(
    body: PrintersUpdateBody,
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
):
    printers = save_printers_config(db, body.printers)
    db.commit()
    return {"printers": printers}
