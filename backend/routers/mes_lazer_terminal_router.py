from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import User
from services.mes_jobs import load_job
from services.mes_lazer_terminal import (
    accept_lazer_job,
    complete_lazer_job,
    get_lazer_stage,
    list_lazer_queue,
    serialize_terminal_job,
    start_lazer_job,
    update_lazer_quantities,
)
from services.permissions import user_has_permission

router = APIRouter(prefix="/mes/terminal/lazer", tags=["mes-terminal-lazer"])


class BomQuantityItem(BaseModel):
    bom_line_id: int
    completed_quantity: float = Field(ge=0)


class QuantitiesUpdate(BaseModel):
    lines: list[BomQuantityItem]


def _require_lazer_terminal(db: Session, user: User) -> None:
    if user_has_permission(db, user, "mes_terminal_lazer"):
        return
    raise HTTPException(status_code=403, detail="Permission required: mes_terminal_lazer")


def _lazer_stage_or_404(db: Session):
    stage = get_lazer_stage(db)
    if not stage:
        raise HTTPException(status_code=503, detail="Lazer production stage is not configured")
    return stage


@router.get("/queue")
def lazer_queue(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_lazer_terminal(db, user)
    stage = _lazer_stage_or_404(db)
    jobs = list_lazer_queue(db, stage.id)
    return {"stage": {"id": stage.id, "name": stage.name, "department": stage.department}, "jobs": jobs}


@router.get("/jobs/{job_id}")
def lazer_job_detail(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_lazer_terminal(db, user)
    stage = _lazer_stage_or_404(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize_terminal_job(job, stage.id, include_bom=True)


@router.post("/jobs/{job_id}/accept")
def lazer_accept_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_lazer_terminal(db, user)
    stage = _lazer_stage_or_404(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        accept_lazer_job(db, job, stage.id, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_job(db, job_id), stage.id, include_bom=True)


@router.post("/jobs/{job_id}/start")
def lazer_start_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_lazer_terminal(db, user)
    stage = _lazer_stage_or_404(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        start_lazer_job(db, job, stage.id, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_job(db, job_id), stage.id, include_bom=True)


@router.post("/jobs/{job_id}/complete")
def lazer_complete_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_lazer_terminal(db, user)
    stage = _lazer_stage_or_404(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        complete_lazer_job(db, job, stage.id, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_job(db, job_id), stage.id, include_bom=True)


@router.put("/jobs/{job_id}/quantities")
def lazer_update_quantities(
    job_id: int,
    data: QuantitiesUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_lazer_terminal(db, user)
    stage = _lazer_stage_or_404(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not data.lines:
        raise HTTPException(status_code=400, detail="No quantity lines provided")
    try:
        auto_completed = update_lazer_quantities(
            db,
            job,
            stage.id,
            user.username,
            [(item.bom_line_id, item.completed_quantity) for item in data.lines],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    payload = serialize_terminal_job(load_job(db, job_id), stage.id, include_bom=True)
    payload["auto_completed"] = auto_completed
    return payload
