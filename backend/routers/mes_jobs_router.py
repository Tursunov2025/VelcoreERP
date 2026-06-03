from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from auth.deps import get_current_user
from database import get_db
from models import MesProductTemplate, MesProductionJob, User
from services.audit import log_action
from services.mes_jobs import (
    apply_status_change,
    generate_job_number,
    load_job,
    normalize_job_number,
    release_job_snapshot,
    serialize_job,
    validate_priority,
)
from services.permissions import user_has_permission

router = APIRouter(prefix="/mes/jobs", tags=["mes-jobs"])


class JobCreate(BaseModel):
    job_number: Optional[str] = None
    customer_name: str = ""
    order_reference: str = ""
    template_id: int
    quantity: float = Field(..., gt=0)
    priority: str = "normal"
    due_date: Optional[datetime] = None


class JobUpdate(BaseModel):
    customer_name: Optional[str] = None
    order_reference: Optional[str] = None
    template_id: Optional[int] = None
    quantity: Optional[float] = Field(None, gt=0)
    priority: Optional[str] = None
    due_date: Optional[datetime] = None


class JobStatusUpdate(BaseModel):
    status: str


def _require_jobs_view(db: Session, user: User) -> None:
    if user_has_permission(db, user, "mes_view") or user_has_permission(
        db, user, "mes_jobs_view"
    ):
        return
    raise HTTPException(status_code=403, detail="Permission required: mes_jobs_view")


def _require_jobs_manage(db: Session, user: User) -> None:
    if user_has_permission(db, user, "mes_edit") or user_has_permission(
        db, user, "mes_jobs_manage"
    ):
        return
    raise HTTPException(status_code=403, detail="Permission required: mes_jobs_manage")


def _get_template(db: Session, template_id: int) -> MesProductTemplate:
    template = (
        db.query(MesProductTemplate)
        .filter(
            MesProductTemplate.id == template_id,
            MesProductTemplate.deleted_at.is_(None),
            MesProductTemplate.is_active.is_(True),
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.get("")
def list_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    q: str = Query(""),
    status: Optional[str] = Query(None),
):
    _require_jobs_view(db, user)
    query = (
        db.query(MesProductionJob)
        .options(
            joinedload(MesProductionJob.template),
            joinedload(MesProductionJob.route),
        )
        .order_by(MesProductionJob.created_at.desc())
    )
    if status:
        query = query.filter(MesProductionJob.status == status)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            MesProductionJob.job_number.ilike(term)
            | MesProductionJob.customer_name.ilike(term)
            | MesProductionJob.order_reference.ilike(term)
        )
    jobs = query.all()
    return {"jobs": [serialize_job(job, include_snapshots=False) for job in jobs]}


@router.get("/{job_id}")
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_jobs_view(db, user)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize_job(job, include_snapshots=True)


@router.post("")
def create_job(
    data: JobCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_jobs_manage(db, user)
    _get_template(db, data.template_id)
    try:
        priority = validate_priority(data.priority)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_number = normalize_job_number(data.job_number) if data.job_number else generate_job_number(db)
    if not job_number:
        job_number = generate_job_number(db)

    existing = (
        db.query(MesProductionJob)
        .filter(MesProductionJob.job_number == job_number)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Job number already exists")

    job = MesProductionJob(
        job_number=job_number,
        customer_name=(data.customer_name or "").strip(),
        order_reference=(data.order_reference or "").strip(),
        template_id=data.template_id,
        quantity=float(data.quantity),
        priority=priority,
        due_date=data.due_date,
        status="draft",
        created_by=user.username,
    )
    db.add(job)
    log_action(db, user.username, "create", "mes_job", details=job_number)
    db.commit()
    return serialize_job(load_job(db, job.id), include_snapshots=True)


@router.put("/{job_id}")
def update_job(
    job_id: int,
    data: JobUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_jobs_manage(db, user)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft jobs can be edited")

    if data.template_id is not None:
        _get_template(db, data.template_id)
        job.template_id = data.template_id
    if data.customer_name is not None:
        job.customer_name = data.customer_name.strip()
    if data.order_reference is not None:
        job.order_reference = data.order_reference.strip()
    if data.quantity is not None:
        job.quantity = float(data.quantity)
    if data.priority is not None:
        try:
            job.priority = validate_priority(data.priority)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if data.due_date is not None:
        job.due_date = data.due_date

    job.updated_at = datetime.utcnow()
    log_action(db, user.username, "update", "mes_job", job_id, job.job_number)
    db.commit()
    return serialize_job(load_job(db, job_id), include_snapshots=True)


@router.post("/{job_id}/release")
def release_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_jobs_manage(db, user)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        release_job_snapshot(db, job)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_action(db, user.username, "release", "mes_job", job_id, job.job_number)
    db.commit()
    return serialize_job(load_job(db, job_id), include_snapshots=True)


@router.put("/{job_id}/status")
def update_job_status(
    job_id: int,
    data: JobStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_jobs_manage(db, user)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        apply_status_change(job, data.status.strip().lower())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_action(
        db,
        user.username,
        "status",
        "mes_job",
        job_id,
        f"{job.job_number} -> {job.status}",
    )
    db.commit()
    return serialize_job(load_job(db, job_id), include_snapshots=True)
