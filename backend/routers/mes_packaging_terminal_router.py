from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import User
from services.mes_packaging_terminal import (
    accept_packaging_job,
    complete_packaging_job,
    get_packaging_stages,
    list_packaging_queue,
    load_packaging_job,
    packaging_dashboard,
    packaging_stage_ids,
    serialize_terminal_job,
    start_packaging_job,
    update_packaging_data,
)
from services.permissions import user_has_permission

router = APIRouter(prefix="/mes/terminal/packaging", tags=["mes-terminal-packaging"])


class PackagingDataUpdate(BaseModel):
    package_type: Optional[str] = None
    package_count: Optional[int] = Field(None, ge=0)
    net_weight_kg: Optional[float] = Field(None, ge=0)
    gross_weight_kg: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None


def _require_packaging_terminal(db: Session, user: User) -> None:
    if user_has_permission(db, user, "mes_terminal_packaging"):
        return
    raise HTTPException(status_code=403, detail="Permission required: mes_terminal_packaging")


def _packaging_stages_or_503(db: Session):
    stages = get_packaging_stages(db)
    if not stages:
        raise HTTPException(status_code=503, detail="Packaging production stages are not configured")
    return stages


@router.get("/dashboard")
def packaging_dashboard_endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_packaging_terminal(db, user)
    stages = _packaging_stages_or_503(db)
    ids = {s.id for s in stages}
    stats = packaging_dashboard(db, ids)
    return {
        "stages": [{"id": s.id, "name": s.name, "department": s.department} for s in stages],
        **stats,
    }


@router.get("/queue")
def packaging_queue(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_packaging_terminal(db, user)
    stages = _packaging_stages_or_503(db)
    ids = {s.id for s in stages}
    jobs = list_packaging_queue(db, ids)
    return {
        "stages": [{"id": s.id, "name": s.name, "department": s.department} for s in stages],
        "jobs": jobs,
    }


@router.get("/jobs/{job_id}")
def packaging_job_detail(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_packaging_terminal(db, user)
    stages = _packaging_stages_or_503(db)
    ids = {s.id for s in stages}
    job = load_packaging_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize_terminal_job(job, ids, include_packages=True)


@router.post("/jobs/{job_id}/accept")
def packaging_accept_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_packaging_terminal(db, user)
    ids = packaging_stage_ids(db)
    job = load_packaging_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        accept_packaging_job(db, job, ids, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_packaging_job(db, job_id), ids, include_packages=True)


@router.post("/jobs/{job_id}/start")
def packaging_start_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_packaging_terminal(db, user)
    ids = packaging_stage_ids(db)
    job = load_packaging_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        start_packaging_job(db, job, ids, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_packaging_job(db, job_id), ids, include_packages=True)


@router.post("/jobs/{job_id}/complete")
def packaging_complete_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_packaging_terminal(db, user)
    ids = packaging_stage_ids(db)
    job = load_packaging_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        complete_packaging_job(db, job, ids, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_packaging_job(db, job_id), ids, include_packages=True)


@router.put("/jobs/{job_id}/packaging-data")
def packaging_update_data(
    job_id: int,
    data: PackagingDataUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_packaging_terminal(db, user)
    ids = packaging_stage_ids(db)
    job = load_packaging_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        update_packaging_data(
            db,
            job,
            ids,
            user.username,
            package_type=data.package_type,
            package_count=data.package_count,
            net_weight_kg=data.net_weight_kg,
            gross_weight_kg=data.gross_weight_kg,
            notes=data.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_packaging_job(db, job_id), ids, include_packages=True)
