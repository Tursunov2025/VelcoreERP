from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import MesTerminalBrigade, MesTerminalBrigadeAssignment, MesTerminalBrigadeMember, ProjectProductionOperation, User, MesProductionStage
from services.production_brigades import (
    attach_participants_to_operation,
    brigade_assigned_to_stage,
    resolve_brigade_for_brigadier,
    user_has_brigade_terminal_access,
    validate_worker_ids,
)
from services.mes_jobs import load_job
from services.mes_yigish_terminal import (
    accept_yigish_job,
    complete_yigish_job,
    get_yigish_stage,
    list_yigish_queue,
    serialize_terminal_job,
    start_yigish_job,
    update_yigish_quantities,
)
from services.permissions import require_project_job_permission, user_has_permission

router = APIRouter(prefix="/mes/terminal/yigish", tags=["mes-terminal-yigish"])


class BomQuantityItem(BaseModel):
    bom_line_id: int
    completed_quantity: float = Field(ge=0)


class QuantitiesUpdate(BaseModel):
    lines: list[BomQuantityItem]


class CompletePayload(BaseModel):
    worker_user_ids: list[int] = Field(default_factory=list)


def _require_yigish_terminal(db: Session, user: User) -> None:
    if user_has_permission(db, user, "mes_terminal_yigish"):
        return

    stage = (
        db.query(MesProductionStage)
        .filter(
            MesProductionStage.name == "Yig‘ish",
            MesProductionStage.is_active.is_(True),
        )
        .first()
    )

    if stage and user_has_brigade_terminal_access(
        db,
        user_id=user.id,
        stage_id=stage.id,
    ):
        return

    raise HTTPException(
        status_code=403,
        detail="Yig‘ish terminaliga faqat brigadir kirishi mumkin",
    )


def _yigish_stage_or_404(db: Session):
    stage = get_yigish_stage(db)
    if not stage:
        raise HTTPException(status_code=503, detail="Yig‘ish production stage is not configured")
    return stage


def _require_yigish_project_execution(
    db: Session,
    user: User,
    job,
    stage_id: int,
) -> None:
    # Root / explicitly authorized project users keep the canonical gate.
    if user_has_permission(db, user, "production_projects_execute"):
        if getattr(getattr(job, "project", None), "status", None) == "cancelled":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "project_cancelled",
                    "message": "Cancelled project cannot accept terminal work",
                },
            )
        return

    # Otherwise execution is granted only through the active Yig‘ish brigade.
    step = next(
        (row for row in (job.route_steps or []) if row.stage_id == stage_id),
        None,
    )
    if not step or not step.brigade_id:
        raise HTTPException(
            status_code=403,
            detail="Job hali Yig‘ish brigadasiga biriktirilmagan",
        )

    if getattr(getattr(job, "project", None), "status", None) == "cancelled":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "project_cancelled",
                "message": "Cancelled project cannot accept terminal work",
            },
        )

    brigade = brigade_assigned_to_stage(
        db,
        brigade_id=step.brigade_id,
        stage_id=stage_id,
    )
    if not brigade:
        raise HTTPException(
            status_code=403,
            detail="Job brigadasi faol emas",
        )

    is_brigadier = brigade.brigadier_user_id == user.id

    is_member = (
        db.query(MesTerminalBrigadeMember.id)
        .filter(
            MesTerminalBrigadeMember.brigade_id == brigade.id,
            MesTerminalBrigadeMember.user_id == user.id,
            MesTerminalBrigadeMember.is_active.is_(True),
        )
        .first()
        is not None
    )

    if not is_brigadier and not is_member:
        raise HTTPException(
            status_code=403,
            detail="Siz ushbu Yig‘ish brigadasi tarkibiga kirmaysiz",
        )


@router.get("/brigade")
def yigish_brigade(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_yigish_terminal(db, user)
    stage = _yigish_stage_or_404(db)

    try:
        brigade = resolve_brigade_for_brigadier(
            db,
            stage_id=stage.id,
            user_id=user.id,
        )
    except ValueError as exc:
        # Terminal foydalanuvchisi worker bo‘lishi ham mumkin.
        # Bunday holatda uning faol brigadaga a’zo ekanini topamiz.
        from models import MesTerminalBrigadeMember

        membership = (
            db.query(MesTerminalBrigadeMember)
            .join(
                MesTerminalBrigade,
                MesTerminalBrigade.id == MesTerminalBrigadeMember.brigade_id,
            )
            .join(
                MesTerminalBrigadeAssignment,
                MesTerminalBrigadeAssignment.brigade_id == MesTerminalBrigade.id,
            )
            .filter(
                MesTerminalBrigadeAssignment.stage_id == stage.id,
                MesTerminalBrigadeAssignment.is_active.is_(True),
                MesTerminalBrigadeMember.user_id == user.id,
                MesTerminalBrigadeMember.is_active.is_(True),
                MesTerminalBrigade.is_active.is_(True),
            )
            .first()
        )

        if not membership:
            raise HTTPException(
                status_code=403,
                detail="Siz Yig‘ish brigadasiga biriktirilmagansiz",
            )

        brigade = brigade_assigned_to_stage(
            db,
            brigade_id=membership.brigade_id,
            stage_id=stage.id,
        )

    members = (
        db.query(User)
        .join(
            MesTerminalBrigadeMember,
            MesTerminalBrigadeMember.user_id == User.id,
        )
        .filter(
            MesTerminalBrigadeMember.brigade_id == brigade.id,
            MesTerminalBrigadeMember.is_active.is_(True),
            User.is_active.is_(True),
            User.id != brigade.brigadier_user_id,
        )
        .all()
    )

    def user_payload(row: User) -> dict:
        from models import UserIdentityProfile

        profile = (
            db.query(UserIdentityProfile)
            .filter(UserIdentityProfile.user_id == row.id)
            .first()
        )
        return {
            "id": row.id,
            "username": row.username,
            "full_name": (profile.full_name if profile else "") or row.username,
            "employee_id": (profile.employee_id if profile else "") or "",
            "position": (profile.position if profile else "") or row.department or "",
        }

    brigadier = (
        db.query(User)
        .filter(User.id == brigade.brigadier_user_id)
        .first()
    )

    return {
        "id": brigade.id,
        "name": brigade.name,
        "stage_id": brigade.stage_id,
        "stage_name": stage.name,
        "is_brigadier": user.id == brigade.brigadier_user_id,
        "brigadier": user_payload(brigadier) if brigadier else None,
        "members": [user_payload(row) for row in members],
    }


@router.get("/queue")
def yigish_queue(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_yigish_terminal(db, user)
    stage = _yigish_stage_or_404(db)
    jobs = list_yigish_queue(db, stage.id)
    return {"stage": {"id": stage.id, "name": stage.name, "department": stage.department}, "jobs": jobs}


@router.get("/jobs/{job_id}")
def yigish_job_detail(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_yigish_terminal(db, user)
    stage = _yigish_stage_or_404(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize_terminal_job(job, stage.id, include_bom=True)


@router.post("/jobs/{job_id}/accept")
def yigish_accept_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_yigish_terminal(db, user)
    stage = _yigish_stage_or_404(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if getattr(getattr(job, "project", None), "status", None) == "cancelled":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "project_cancelled",
                "message": "Cancelled project cannot accept terminal work",
            },
        )
    try:
        brigade = resolve_brigade_for_brigadier(
            db,
            stage_id=stage.id,
            user_id=user.id,
        )
        step = next(
            (row for row in job.route_steps if row.stage_id == stage.id),
            None,
        )
        if not step:
            raise ValueError("Job has no Yig‘ish route step")

        if step.brigade_id and step.brigade_id != brigade.id:
            raise ValueError("Job ushbu brigadaga boshqa brigada tomonidan qabul qilingan")

        step.brigade_id = brigade.id
        step.accepted_by_user_id = user.id

        accept_yigish_job(db, job, stage.id, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_job(db, job_id), stage.id, include_bom=True)


@router.post("/jobs/{job_id}/start")
def yigish_start_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_yigish_terminal(db, user)
    stage = _yigish_stage_or_404(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    _require_yigish_project_execution(db, user, job, stage.id)
    try:
        start_yigish_job(db, job, stage.id, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(load_job(db, job_id), stage.id, include_bom=True)


@router.post("/jobs/{job_id}/complete")
def yigish_complete_job(
    job_id: int,
    data: CompletePayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_yigish_terminal(db, user)
    stage = _yigish_stage_or_404(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    _require_yigish_project_execution(db, user, job, stage.id)

    try:
        step = next(
            (row for row in job.route_steps if row.stage_id == stage.id),
            None,
        )
        if not step:
            raise ValueError("Job has no Yig‘ish route step")
        if not step.brigade_id:
            raise ValueError("Avval brigada orqali topshiriqni qabul qiling")
        if step.accepted_by_user_id != user.id:
            raise ValueError("Faqat topshiriqni qabul qilgan brigadir yakunlashi mumkin")

        brigade = brigade_assigned_to_stage(
            db,
            brigade_id=step.brigade_id,
            stage_id=stage.id,
        )
        if not brigade or not brigade.is_active:
            raise ValueError("Job brigadasi faol emas")

        workers = validate_worker_ids(
            db,
            brigade=brigade,
            worker_user_ids=data.worker_user_ids,
        )

        complete_yigish_job(db, job, stage.id, user.username)

        operations = (
            db.query(ProjectProductionOperation)
            .filter(
                ProjectProductionOperation.job_id == job.id,
                ProjectProductionOperation.route_step_id == step.id,
            )
            .all()
        )

        now = step.completed_at
        for operation in operations:
            attach_participants_to_operation(
                db,
                operation=operation,
                brigade=brigade,
                brigadier=user,
                workers=workers,
                started_at=step.started_at,
                completed_at=now,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return serialize_terminal_job(load_job(db, job_id), stage.id, include_bom=True)


@router.put("/jobs/{job_id}/quantities")
def yigish_update_quantities(
    job_id: int,
    data: QuantitiesUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_yigish_terminal(db, user)
    stage = _yigish_stage_or_404(db)
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    _require_yigish_project_execution(db, user, job, stage.id)
    if not data.lines:
        raise HTTPException(status_code=400, detail="No quantity lines provided")
    try:
        auto_completed = update_yigish_quantities(
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
    payload["surplus_candidates"] = [
        {"bom_line_id": line.id, "part_number": line.part_number, "part_name": line.part_name,
         "required_quantity": float(line.allocated_quantity or 0), "completed_quantity": float(line.completed_quantity or 0),
         "surplus_quantity": float(line.completed_quantity or 0) - float(line.allocated_quantity or 0) - float(line.surplus_stocked_quantity or 0)}
        for line in (load_job(db, job_id).bom_lines or []) if float(line.completed_quantity or 0) - float(line.allocated_quantity or 0) - float(line.surplus_stocked_quantity or 0) > 0
    ]
    return payload
