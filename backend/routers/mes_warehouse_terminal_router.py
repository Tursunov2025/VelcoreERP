from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import MesWarehouseLocation, User
from services.mes_warehouse_terminal import (
    accept_warehouse_receipt,
    assign_package_to_location,
    complete_warehouse_receipt,
    create_location,
    get_warehouse_stages,
    list_inventory_summary,
    list_locations,
    list_warehouse_queue,
    load_warehouse_job,
    serialize_terminal_job,
    start_warehouse_placement,
    update_location,
    warehouse_dashboard,
    warehouse_stage_ids,
)
from services.permissions import user_has_permission

router = APIRouter(prefix="/mes/terminal/warehouse", tags=["mes-terminal-warehouse"])
admin_router = APIRouter(prefix="/mes/warehouse", tags=["mes-warehouse-admin"])


class PlacePackageRequest(BaseModel):
    location_id: int


class LocationCreate(BaseModel):
    code: str = Field(..., min_length=1)
    description: str = ""


class LocationUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


def _require_warehouse_terminal(db: Session, user: User) -> None:
    if user_has_permission(db, user, "mes_terminal_warehouse"):
        return
    raise HTTPException(status_code=403, detail="Permission required: mes_terminal_warehouse")


def _require_mes_edit(db: Session, user: User) -> None:
    if user.role == "admin" or user_has_permission(db, user, "mes_edit"):
        return
    raise HTTPException(status_code=403, detail="Permission required: mes_edit")


def _warehouse_stages_or_503(db: Session):
    stages = get_warehouse_stages(db)
    if not stages:
        raise HTTPException(status_code=503, detail="Warehouse production stages are not configured")
    return stages


@router.get("/dashboard")
def warehouse_dashboard_endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_warehouse_terminal(db, user)
    stages = _warehouse_stages_or_503(db)
    ids = {s.id for s in stages}
    stats = warehouse_dashboard(db, ids)
    return {
        "stages": [{"id": s.id, "name": s.name, "department": s.department} for s in stages],
        **stats,
    }


@router.get("/queue")
def warehouse_queue(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_warehouse_terminal(db, user)
    stages = _warehouse_stages_or_503(db)
    ids = {s.id for s in stages}
    jobs = list_warehouse_queue(db, ids)
    return {
        "stages": [{"id": s.id, "name": s.name, "department": s.department} for s in stages],
        "jobs": jobs,
    }


@router.get("/inventory")
def warehouse_inventory(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_warehouse_terminal(db, user)
    return {"items": list_inventory_summary(db)}


@router.get("/locations")
def warehouse_locations_list(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_warehouse_terminal(db, user)
    return {"locations": list_locations(db, include_inactive=False)}


@router.get("/jobs/{job_id}")
def warehouse_job_detail(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_warehouse_terminal(db, user)
    stages = _warehouse_stages_or_503(db)
    ids = {s.id for s in stages}
    job = load_warehouse_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize_terminal_job(job, ids, include_packages=True)


@router.post("/jobs/{job_id}/accept")
def warehouse_accept_receipt(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_warehouse_terminal(db, user)
    ids = warehouse_stage_ids(db)
    job = load_warehouse_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        accept_warehouse_receipt(db, job, ids, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_warehouse_job(db, job_id), ids, include_packages=True)


@router.post("/jobs/{job_id}/start")
def warehouse_start_placement(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_warehouse_terminal(db, user)
    ids = warehouse_stage_ids(db)
    job = load_warehouse_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        start_warehouse_placement(db, job, ids, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_warehouse_job(db, job_id), ids, include_packages=True)


@router.post("/jobs/{job_id}/complete")
def warehouse_complete_receipt(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_warehouse_terminal(db, user)
    ids = warehouse_stage_ids(db)
    job = load_warehouse_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        complete_warehouse_receipt(db, job, ids, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_warehouse_job(db, job_id), ids, include_packages=True)


@router.post("/jobs/{job_id}/packages/{package_id}/place")
def warehouse_place_package(
    job_id: int,
    package_id: int,
    data: PlacePackageRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_warehouse_terminal(db, user)
    ids = warehouse_stage_ids(db)
    job = load_warehouse_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        assign_package_to_location(
            db,
            job,
            ids,
            user.username,
            package_id=package_id,
            location_id=data.location_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_warehouse_job(db, job_id), ids, include_packages=True)


# --- Admin location management ---


@admin_router.get("/locations")
def admin_list_locations(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_mes_edit(db, user)
    return {"locations": list_locations(db, include_inactive=include_inactive)}


@admin_router.post("/locations")
def admin_create_location(
    data: LocationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_mes_edit(db, user)
    try:
        loc = create_location(db, user.username, data.code, data.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return loc


@admin_router.put("/locations/{location_id}")
def admin_update_location(
    location_id: int,
    data: LocationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_mes_edit(db, user)
    loc = db.query(MesWarehouseLocation).filter(MesWarehouseLocation.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    try:
        updated = update_location(
            db,
            loc,
            user.username,
            code=data.code,
            description=data.description,
            is_active=data.is_active,
            sort_order=data.sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return updated
