from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import User
from services.mes_jobs import load_job
from services.mes_svarshik_terminal import (
    accept_welding_job,
    complete_welding_job,
    get_welding_stages,
    list_welding_queue,
    serialize_terminal_job,
    start_welding_job,
    update_welding_quantities,
    welding_dashboard,
    welding_stage_ids,
)
from services.permissions import user_has_permission

router = APIRouter(prefix="/mes/terminal/svarshik", tags=["mes-terminal-svarshik"])


class BomQuantityItem(BaseModel):
    bom_line_id: int
    completed_quantity: Optional[float] = Field(None, ge=0)
    accepted_quantity: Optional[float] = Field(None, ge=0)
    rejected_quantity: Optional[float] = Field(None, ge=0)


class QuantitiesUpdate(BaseModel):
    lines: list[BomQuantityItem]


def _require_svarshik_terminal(db: Session, user: User) -> None:
    if user_has_permission(db, user, "mes_terminal_svarshik"):
        return
    raise HTTPException(status_code=403, detail="Permission required: mes_terminal_svarshik")


def _welding_stages_or_503(db: Session):
    stages = get_welding_stages(db)
    if not stages:
        raise HTTPException(status_code=503, detail="Welding production stages are not configured")
    return stages


@router.get("/dashboard")
def svarshik_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_svarshik_terminal(db, user)
    stages = _welding_stages_or_503(db)
    ids = {s.id for s in stages}
    stats = welding_dashboard(db, ids)
    return {
        "stages": [{"id": s.id, "name": s.name, "department": s.department} for s in stages],
        **stats,
    }


@router.get("/queue")
def svarshik_queue(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_svarshik_terminal(db, user)
    stages = _welding_stages_or_503(db)
    ids = {s.id for s in stages}
    jobs = list_welding_queue(db, ids)
    return {
        "stages": [{"id": s.id, "name": s.name, "department": s.department} for s in stages],
        "jobs": jobs,
    }


@router.get("/jobs/{job_id}")
def svarshik_job_detail(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_svarshik_terminal(db, user)
    stages = _welding_stages_or_503(db)
    ids = {s.id for s in stages}
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize_terminal_job(job, ids, include_bom=True)


@router.post("/jobs/{job_id}/accept")
def svarshik_accept_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_svarshik_terminal(db, user)
    ids = welding_stage_ids(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        accept_welding_job(db, job, ids, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_job(db, job_id), ids, include_bom=True)


@router.post("/jobs/{job_id}/start")
def svarshik_start_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_svarshik_terminal(db, user)
    ids = welding_stage_ids(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        start_welding_job(db, job, ids, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_job(db, job_id), ids, include_bom=True)


@router.post("/jobs/{job_id}/complete")
def svarshik_complete_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_svarshik_terminal(db, user)
    ids = welding_stage_ids(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        complete_welding_job(db, job, ids, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_job(db, job_id), ids, include_bom=True)


@router.put("/jobs/{job_id}/quantities")
def svarshik_update_quantities(
    job_id: int,
    data: QuantitiesUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_svarshik_terminal(db, user)
    ids = welding_stage_ids(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not data.lines:
        raise HTTPException(status_code=400, detail="No quantity lines provided")
    try:
        payload_lines = [item.model_dump(exclude_none=True) for item in data.lines]
        auto_completed = update_welding_quantities(db, job, ids, user.username, payload_lines)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    result = serialize_terminal_job(load_job(db, job_id), ids, include_bom=True)
    result["auto_completed"] = auto_completed
    return result
