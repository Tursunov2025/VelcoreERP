"""Lazer shop-floor terminal — queue, quantities, step transitions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from models import MesJobBomLine, MesJobRouteStep, MesProductionJob, MesProductionStage
from services.audit import log_value_change
from services.mes_jobs import load_job

LAZER_STAGE_NAME = "Lazer"
QUEUE_JOB_STATUSES = ("released", "in_progress")
PRIORITY_RANK = {"urgent": 0, "high": 1, "normal": 2, "low": 3}


def get_lazer_stage(db: Session) -> MesProductionStage | None:
    return (
        db.query(MesProductionStage)
        .filter(
            MesProductionStage.name == LAZER_STAGE_NAME,
            MesProductionStage.is_active.is_(True),
        )
        .first()
    )


def ordered_steps(job: MesProductionJob) -> list[MesJobRouteStep]:
    return sorted(job.route_steps or [], key=lambda step: (step.step_order, step.id))


def get_active_step(job: MesProductionJob) -> MesJobRouteStep | None:
    for step in ordered_steps(job):
        if step.is_required and step.completed_at is None:
            return step
    return None


def get_lazer_step(job: MesProductionJob, lazer_stage_id: int) -> MesJobRouteStep | None:
    return next((s for s in ordered_steps(job) if s.stage_id == lazer_stage_id), None)


def prior_steps_complete(job: MesProductionJob, step: MesJobRouteStep) -> bool:
    for prior in ordered_steps(job):
        if prior.step_order >= step.step_order:
            break
        if prior.is_required and prior.completed_at is None:
            return False
    return True


def job_in_lazer_queue(job: MesProductionJob, lazer_stage_id: int) -> bool:
    if job.status not in QUEUE_JOB_STATUSES:
        return False
    active = get_active_step(job)
    if not active or active.stage_id != lazer_stage_id:
        return False
    return prior_steps_complete(job, active)


def lazer_step_state(step: MesJobRouteStep | None) -> str:
    if not step:
        return "missing"
    if step.completed_at:
        return "completed"
    if step.started_at:
        return "in_progress"
    if step.accepted_at:
        return "accepted"
    return "pending_accept"


def bom_line_progress_pct(line: MesJobBomLine) -> float:
    allocated = float(line.allocated_quantity or 0)
    if allocated <= 0:
        return 100.0
    completed = float(line.completed_quantity or 0)
    return min(100.0, round((completed / allocated) * 100.0, 2))


def job_lazer_progress_pct(job: MesProductionJob) -> float:
    lines = [line for line in (job.bom_lines or []) if float(line.allocated_quantity or 0) > 0]
    if not lines:
        return 0.0
    total_allocated = sum(float(line.allocated_quantity or 0) for line in lines)
    if total_allocated <= 0:
        return 0.0
    total_completed = sum(float(line.completed_quantity or 0) for line in lines)
    return min(100.0, round((total_completed / total_allocated) * 100.0, 2))


def count_completed_bom_lines(job: MesProductionJob) -> int:
    count = 0
    for line in job.bom_lines or []:
        allocated = float(line.allocated_quantity or 0)
        completed = float(line.completed_quantity or 0)
        if allocated <= 0 or completed >= allocated:
            count += 1
    return count


def serialize_bom_line_terminal(line: MesJobBomLine) -> dict:
    progress = bom_line_progress_pct(line)
    return {
        "id": line.id,
        "part_id": line.part_id,
        "part_number": line.part_number,
        "part_name": line.part_name,
        "unit": line.unit,
        "allocated_quantity": float(line.allocated_quantity or 0),
        "completed_quantity": float(line.completed_quantity or 0),
        "accepted_quantity": float(line.accepted_quantity or 0),
        "rejected_quantity": float(line.rejected_quantity or 0),
        "drawing_url": line.drawing_url,
        "notes": line.notes or "",
        "sort_order": line.sort_order,
        "progress_pct": progress,
        "is_laser_relevant": True,
    }


def serialize_lazer_step(step: MesJobRouteStep | None) -> dict | None:
    if not step:
        return None
    return {
        "id": step.id,
        "stage_id": step.stage_id,
        "stage_name": step.stage_name,
        "step_order": step.step_order,
        "department": step.department,
        "responsible_role": step.responsible_role,
        "estimated_minutes": step.estimated_minutes,
        "required_parts_count": int(step.required_parts_count or 0),
        "completed_parts_count": int(step.completed_parts_count or 0),
        "started_at": step.started_at,
        "accepted_at": step.accepted_at,
        "completed_at": step.completed_at,
        "instructions": step.instructions or "",
        "state": lazer_step_state(step),
    }


def serialize_terminal_job(
    job: MesProductionJob,
    lazer_stage_id: int,
    *,
    include_bom: bool = True,
) -> dict:
    lazer_step = get_lazer_step(job, lazer_stage_id)
    bom_lines = sorted(job.bom_lines or [], key=lambda line: (line.sort_order, line.id))
    laser_parts = [line for line in bom_lines if float(line.allocated_quantity or 0) > 0]
    payload = {
        "id": job.id,
        "job_number": job.job_number,
        "customer_name": job.customer_name or "",
        "order_reference": job.order_reference or "",
        "template_id": job.template_id,
        "template_code": job.template.code if job.template else None,
        "template_name": job.template.name if job.template else None,
        "quantity": float(job.quantity or 0),
        "priority": job.priority or "normal",
        "due_date": job.due_date,
        "status": job.status,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
        "lazer_step": serialize_lazer_step(lazer_step),
        "step_state": lazer_step_state(lazer_step),
        "overall_progress_pct": job_lazer_progress_pct(job),
        "bom_line_count": len(bom_lines),
        "laser_part_count": len(laser_parts),
    }
    if include_bom:
        payload["bom_lines"] = [serialize_bom_line_terminal(line) for line in bom_lines]
        payload["laser_parts"] = [serialize_bom_line_terminal(line) for line in laser_parts]
    return payload


def list_lazer_queue(db: Session, lazer_stage_id: int) -> list[dict]:
    jobs = (
        db.query(MesProductionJob)
        .options(
            joinedload(MesProductionJob.template),
            joinedload(MesProductionJob.bom_lines),
            joinedload(MesProductionJob.route_steps),
        )
        .filter(MesProductionJob.status.in_(QUEUE_JOB_STATUSES))
        .all()
    )
    queue = []
    for job in jobs:
        if not job_in_lazer_queue(job, lazer_stage_id):
            continue
        queue.append(serialize_terminal_job(job, lazer_stage_id, include_bom=False))
    queue.sort(
        key=lambda item: (
            PRIORITY_RANK.get(item.get("priority") or "normal", 2),
            item.get("due_date") or datetime.max,
            item.get("created_at") or datetime.max,
        )
    )
    return queue


def _require_lazer_step(
    job: MesProductionJob, lazer_stage_id: int
) -> MesJobRouteStep:
    if job.status not in QUEUE_JOB_STATUSES:
        raise ValueError("Job is not active for terminal work")
    step = get_lazer_step(job, lazer_stage_id)
    if not step:
        raise ValueError("Job has no Lazer route step")
    active = get_active_step(job)
    if not active or active.id != step.id:
        raise ValueError("Job is not waiting at Lazer stage")
    if step.completed_at:
        raise ValueError("Lazer stage already completed")
    return step


def accept_lazer_job(db: Session, job: MesProductionJob, lazer_stage_id: int, username: str) -> None:
    step = _require_lazer_step(job, lazer_stage_id)
    if step.accepted_at:
        raise ValueError("Job already accepted")
    now = datetime.utcnow()
    log_value_change(
        db,
        username,
        "accept",
        "mes_job_route_step",
        step.id,
        "accepted_at",
        None,
        now.isoformat(),
    )
    step.accepted_at = now
    job.updated_at = now


def start_lazer_job(db: Session, job: MesProductionJob, lazer_stage_id: int, username: str) -> None:
    step = _require_lazer_step(job, lazer_stage_id)
    if not step.accepted_at:
        raise ValueError("Accept the job before starting work")
    if step.started_at:
        raise ValueError("Work already started")
    from services.material_auto_consumption import auto_consume_on_stage_start

    auto_consume_on_stage_start(db, job, "Lazer", username)
    now = datetime.utcnow()
    log_value_change(
        db,
        username,
        "start",
        "mes_job_route_step",
        step.id,
        "started_at",
        None,
        now.isoformat(),
    )
    step.started_at = now
    if job.status == "released":
        old_status = job.status
        job.status = "in_progress"
        log_value_change(
            db,
            username,
            "status",
            "mes_production_job",
            job.id,
            "status",
            old_status,
            job.status,
        )
        if job.started_at is None:
            job.started_at = now
    job.updated_at = now


def _complete_lazer_step(
    db: Session,
    job: MesProductionJob,
    step: MesJobRouteStep,
    username: str,
    *,
    auto: bool = False,
) -> None:
    if step.completed_at:
        return
    progress = job_lazer_progress_pct(job)
    if progress < 100.0:
        raise ValueError("Lazer progress must reach 100% before completing")

    now = datetime.utcnow()
    old_completed_at = step.completed_at.isoformat() if step.completed_at else None
    step.completed_at = now
    step.completed_parts_count = max(
        int(step.completed_parts_count or 0),
        count_completed_bom_lines(job),
        int(step.required_parts_count or 0) if int(step.required_parts_count or 0) > 0 else count_completed_bom_lines(job),
    )
    log_value_change(
        db,
        username,
        "auto_complete" if auto else "complete",
        "mes_job_route_step",
        step.id,
        "completed_at",
        old_completed_at,
        now.isoformat(),
    )

    remaining = [s for s in ordered_steps(job) if s.is_required and s.completed_at is None]
    if not remaining:
        old_status = job.status
        job.status = "completed"
        job.completed_at = now
        log_value_change(
            db,
            username,
            "status",
            "mes_production_job",
            job.id,
            "status",
            old_status,
            job.status,
        )
    job.updated_at = now


def complete_lazer_job(db: Session, job: MesProductionJob, lazer_stage_id: int, username: str) -> None:
    step = _require_lazer_step(job, lazer_stage_id)
    if not step.started_at:
        raise ValueError("Start work before completing")
    _complete_lazer_step(db, job, step, username, auto=False)


def update_lazer_quantities(
    db: Session,
    job: MesProductionJob,
    lazer_stage_id: int,
    username: str,
    updates: list[tuple[int, float]],
) -> bool:
    step = _require_lazer_step(job, lazer_stage_id)
    if not step.started_at:
        raise ValueError("Start work before entering quantities")

    line_map = {line.id: line for line in (job.bom_lines or [])}
    now = datetime.utcnow()
    changed = False

    for bom_line_id, new_qty in updates:
        line = line_map.get(bom_line_id)
        if not line:
            raise ValueError(f"BOM line {bom_line_id} not found on job")
        allocated = float(line.allocated_quantity or 0)
        qty = max(0.0, float(new_qty))
        if allocated > 0 and qty > allocated:
            raise ValueError(
                f"Completed quantity cannot exceed allocated ({line.part_number})"
            )
        old_qty = float(line.completed_quantity or 0)
        if old_qty == qty:
            continue
        log_value_change(
            db,
            username,
            "quantity",
            "mes_job_bom_line",
            line.id,
            "completed_quantity",
            old_qty,
            qty,
        )
        line.completed_quantity = qty
        changed = True

    if changed:
        job.updated_at = now
        step.completed_parts_count = count_completed_bom_lines(job)

    auto_completed = False
    if job_lazer_progress_pct(job) >= 100.0:
        _complete_lazer_step(db, job, step, username, auto=True)
        auto_completed = True

    return auto_completed
