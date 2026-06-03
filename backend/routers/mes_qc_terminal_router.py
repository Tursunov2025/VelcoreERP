from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import MesJobRework, MesQcRejectionReason, User
from services.mes_jobs import load_job
from services.mes_qc_terminal import (
    accept_qc_job,
    complete_qc_job,
    complete_rework,
    create_rejection_reason,
    create_rework_record,
    get_qc_stages,
    list_qc_queue,
    list_rejection_reasons,
    list_rework_queue,
    load_job_reworks,
    qc_dashboard,
    qc_stage_ids,
    serialize_terminal_job,
    start_qc_job,
    start_rework,
    update_qc_quantities,
    update_rejection_reason,
)
from services.permissions import user_has_permission

router = APIRouter(prefix="/mes/terminal/qc", tags=["mes-terminal-qc"])
admin_router = APIRouter(prefix="/mes/qc", tags=["mes-qc-admin"])


class BomQuantityItem(BaseModel):
    bom_line_id: int
    accepted_quantity: Optional[float] = Field(None, ge=0)
    rejected_quantity: Optional[float] = Field(None, ge=0)
    rework_quantity: Optional[float] = Field(None, ge=0)


class QuantitiesUpdate(BaseModel):
    lines: list[BomQuantityItem]


class ReworkCreate(BaseModel):
    bom_line_id: int
    quantity: float = Field(..., gt=0)
    rejection_reason_id: Optional[int] = None
    notes: str = ""


class RejectionReasonCreate(BaseModel):
    name: str = Field(..., min_length=1)
    sort_order: int = 0


class RejectionReasonUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


def _require_qc_terminal(db: Session, user: User) -> None:
    if user_has_permission(db, user, "mes_terminal_qc"):
        return
    raise HTTPException(status_code=403, detail="Permission required: mes_terminal_qc")


def _require_mes_edit(db: Session, user: User) -> None:
    if user.role == "admin" or user_has_permission(db, user, "mes_edit"):
        return
    raise HTTPException(status_code=403, detail="Permission required: mes_edit")


def _qc_stages_or_503(db: Session):
    stages = get_qc_stages(db)
    if not stages:
        raise HTTPException(status_code=503, detail="QC production stages are not configured")
    return stages


@router.get("/dashboard")
def qc_dashboard_endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_qc_terminal(db, user)
    stages = _qc_stages_or_503(db)
    ids = {s.id for s in stages}
    stats = qc_dashboard(db, ids)
    return {
        "stages": [{"id": s.id, "name": s.name, "department": s.department} for s in stages],
        **stats,
    }


@router.get("/queue")
def qc_queue(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_qc_terminal(db, user)
    stages = _qc_stages_or_503(db)
    ids = {s.id for s in stages}
    jobs = list_qc_queue(db, ids)
    return {
        "stages": [{"id": s.id, "name": s.name, "department": s.department} for s in stages],
        "jobs": jobs,
    }


@router.get("/rework-queue")
def qc_rework_queue(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_qc_terminal(db, user)
    return {"records": list_rework_queue(db)}


@router.get("/rejection-reasons")
def qc_rejection_reasons_list(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_qc_terminal(db, user)
    return {"reasons": list_rejection_reasons(db, include_inactive=False)}


@router.get("/jobs/{job_id}")
def qc_job_detail(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_qc_terminal(db, user)
    stages = _qc_stages_or_503(db)
    ids = {s.id for s in stages}
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    reworks = load_job_reworks(db, job_id)
    return serialize_terminal_job(job, ids, include_bom=True, rework_records=reworks)


@router.post("/jobs/{job_id}/accept")
def qc_accept_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_qc_terminal(db, user)
    ids = qc_stage_ids(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        accept_qc_job(db, job, ids, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    reworks = load_job_reworks(db, job_id)
    return serialize_terminal_job(load_job(db, job_id), ids, include_bom=True, rework_records=reworks)


@router.post("/jobs/{job_id}/start")
def qc_start_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_qc_terminal(db, user)
    ids = qc_stage_ids(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        start_qc_job(db, job, ids, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    reworks = load_job_reworks(db, job_id)
    return serialize_terminal_job(load_job(db, job_id), ids, include_bom=True, rework_records=reworks)


@router.post("/jobs/{job_id}/complete")
def qc_complete_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_qc_terminal(db, user)
    ids = qc_stage_ids(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        complete_qc_job(db, job, ids, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    reworks = load_job_reworks(db, job_id)
    return serialize_terminal_job(load_job(db, job_id), ids, include_bom=True, rework_records=reworks)


@router.put("/jobs/{job_id}/quantities")
def qc_update_quantities(
    job_id: int,
    data: QuantitiesUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_qc_terminal(db, user)
    ids = qc_stage_ids(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not data.lines:
        raise HTTPException(status_code=400, detail="No quantity lines provided")
    try:
        payload_lines = [item.model_dump(exclude_none=True) for item in data.lines]
        auto_completed = update_qc_quantities(db, job, ids, user.username, payload_lines)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    reworks = load_job_reworks(db, job_id)
    result = serialize_terminal_job(load_job(db, job_id), ids, include_bom=True, rework_records=reworks)
    result["auto_completed"] = auto_completed
    return result


@router.post("/jobs/{job_id}/rework")
def qc_create_rework(
    job_id: int,
    data: ReworkCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_qc_terminal(db, user)
    ids = qc_stage_ids(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        record = create_rework_record(
            db,
            job,
            ids,
            user.username,
            bom_line_id=data.bom_line_id,
            quantity=data.quantity,
            rejection_reason_id=data.rejection_reason_id,
            notes=data.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    reworks = load_job_reworks(db, job_id)
    result = serialize_terminal_job(load_job(db, job_id), ids, include_bom=True, rework_records=reworks)
    result["created_rework_id"] = record.id
    return result


@router.post("/rework/{rework_id}/start")
def qc_start_rework(
    rework_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_qc_terminal(db, user)
    record = db.query(MesJobRework).filter(MesJobRework.id == rework_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Rework record not found")
    try:
        start_rework(db, record, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {"ok": True, "id": rework_id, "status": "in_progress"}


@router.post("/rework/{rework_id}/complete")
def qc_complete_rework(
    rework_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_qc_terminal(db, user)
    record = db.query(MesJobRework).filter(MesJobRework.id == rework_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Rework record not found")
    try:
        complete_rework(db, record, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {"ok": True, "id": rework_id, "status": "completed"}


# --- Admin rejection reasons ---


@admin_router.get("/rejection-reasons")
def admin_list_rejection_reasons(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_mes_edit(db, user)
    return {"reasons": list_rejection_reasons(db, include_inactive=include_inactive)}


@admin_router.post("/rejection-reasons")
def admin_create_rejection_reason(
    data: RejectionReasonCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_mes_edit(db, user)
    try:
        reason = create_rejection_reason(db, user.username, data.name, data.sort_order)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return reason


@admin_router.put("/rejection-reasons/{reason_id}")
def admin_update_rejection_reason(
    reason_id: int,
    data: RejectionReasonUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_mes_edit(db, user)
    reason = db.query(MesQcRejectionReason).filter(MesQcRejectionReason.id == reason_id).first()
    if not reason:
        raise HTTPException(status_code=404, detail="Rejection reason not found")
    try:
        updated = update_rejection_reason(
            db,
            reason,
            user.username,
            name=data.name,
            sort_order=data.sort_order,
            is_active=data.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return updated
