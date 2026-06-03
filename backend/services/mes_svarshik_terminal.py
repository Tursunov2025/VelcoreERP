"""Svarshik (welding) shop-floor terminal."""

from __future__ import annotations

from datetime import datetime, time

from sqlalchemy.orm import Session, joinedload

from models import MesJobBomLine, MesJobRouteStep, MesProductionJob, MesProductionStage
from services.audit import log_value_change
from services.mes_jobs import load_job
from services.mes_terminal_common import (
    QUEUE_JOB_STATUSES,
    get_active_step,
    ordered_steps,
    prior_steps_complete,
    serialize_route_step,
    sort_queue,
    terminal_step_state,
)

WELDING_DEPARTMENT = "Svarka"
SVARSHIK_STAGE_NAME = "Svarshik"


def get_welding_stages(db: Session) -> list[MesProductionStage]:
    return (
        db.query(MesProductionStage)
        .filter(
            MesProductionStage.is_active.is_(True),
            MesProductionStage.department == WELDING_DEPARTMENT,
        )
        .order_by(MesProductionStage.sort_order, MesProductionStage.name)
        .all()
    )


def welding_stage_ids(db: Session) -> set[int]:
    return {stage.id for stage in get_welding_stages(db)}


def get_current_welding_step(
    job: MesProductionJob, welding_ids: set[int]
) -> MesJobRouteStep | None:
    active = get_active_step(job)
    if active and active.stage_id in welding_ids:
        return active
    return None


def find_welding_step(job: MesProductionJob, welding_ids: set[int]) -> MesJobRouteStep | None:
    current = get_current_welding_step(job, welding_ids)
    if current:
        return current
    return next((s for s in ordered_steps(job) if s.stage_id in welding_ids), None)


def job_in_welding_queue(job: MesProductionJob, welding_ids: set[int]) -> bool:
    if job.status not in QUEUE_JOB_STATUSES:
        return False
    active = get_active_step(job)
    if not active or active.stage_id not in welding_ids:
        return False
    return prior_steps_complete(job, active)


def bom_line_progress_pct(line: MesJobBomLine) -> float:
    allocated = float(line.allocated_quantity or 0)
    if allocated <= 0:
        return 100.0
    accepted = float(line.accepted_quantity or 0)
    return min(100.0, round((accepted / allocated) * 100.0, 2))


def job_welding_progress_pct(job: MesProductionJob) -> float:
    lines = [line for line in (job.bom_lines or []) if float(line.allocated_quantity or 0) > 0]
    if not lines:
        return 0.0
    total_allocated = sum(float(line.allocated_quantity or 0) for line in lines)
    if total_allocated <= 0:
        return 0.0
    total_accepted = sum(float(line.accepted_quantity or 0) for line in lines)
    return min(100.0, round((total_accepted / total_allocated) * 100.0, 2))


def count_accepted_bom_lines(job: MesProductionJob) -> int:
    count = 0
    for line in job.bom_lines or []:
        allocated = float(line.allocated_quantity or 0)
        accepted = float(line.accepted_quantity or 0)
        if allocated <= 0 or accepted >= allocated:
            count += 1
    return count


def serialize_bom_line_terminal(line: MesJobBomLine) -> dict:
    allocated = float(line.allocated_quantity or 0)
    return {
        "id": line.id,
        "part_id": line.part_id,
        "part_number": line.part_number,
        "part_name": line.part_name,
        "unit": line.unit,
        "allocated_quantity": allocated,
        "completed_quantity": float(line.completed_quantity or 0),
        "accepted_quantity": float(line.accepted_quantity or 0),
        "rejected_quantity": float(line.rejected_quantity or 0),
        "drawing_url": line.drawing_url,
        "notes": line.notes or "",
        "sort_order": line.sort_order,
        "progress_pct": bom_line_progress_pct(line),
        "is_welding_relevant": True,
    }


def serialize_terminal_job(
    job: MesProductionJob,
    welding_ids: set[int],
    *,
    include_bom: bool = True,
) -> dict:
    welding_step = find_welding_step(job, welding_ids)
    current_step = get_current_welding_step(job, welding_ids) or welding_step
    bom_lines = sorted(job.bom_lines or [], key=lambda line: (line.sort_order, line.id))
    welding_parts = [line for line in bom_lines if float(line.allocated_quantity or 0) > 0]
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
        "welding_step": serialize_route_step(current_step),
        "step_state": terminal_step_state(current_step),
        "overall_progress_pct": job_welding_progress_pct(job),
        "bom_line_count": len(bom_lines),
        "welding_part_count": len(welding_parts),
    }
    if include_bom:
        payload["bom_lines"] = [serialize_bom_line_terminal(line) for line in bom_lines]
        payload["welding_parts"] = [serialize_bom_line_terminal(line) for line in welding_parts]
    return payload


def list_welding_queue(db: Session, welding_ids: set[int]) -> list[dict]:
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
        if not job_in_welding_queue(job, welding_ids):
            continue
        queue.append(serialize_terminal_job(job, welding_ids, include_bom=False))
    return sort_queue(queue)


def welding_dashboard(db: Session, welding_ids: set[int]) -> dict:
    queue = list_welding_queue(db, welding_ids)
    active = sum(1 for job in queue if job.get("step_state") == "in_progress")
    waiting = sum(1 for job in queue if job.get("step_state") in ("pending_accept", "accepted"))

    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    completed_today = 0
    steps = (
        db.query(MesJobRouteStep)
        .filter(
            MesJobRouteStep.stage_id.in_(welding_ids),
            MesJobRouteStep.completed_at.isnot(None),
            MesJobRouteStep.completed_at >= today_start,
        )
        .count()
    )
    completed_today = steps

    return {
        "active_jobs": active,
        "waiting_jobs": waiting,
        "completed_today": completed_today,
    }


def _require_welding_step(job: MesProductionJob, welding_ids: set[int]) -> MesJobRouteStep:
    if job.status not in QUEUE_JOB_STATUSES:
        raise ValueError("Job is not active for terminal work")
    step = get_current_welding_step(job, welding_ids)
    if not step:
        raise ValueError("Job is not waiting at welding stage")
    if step.completed_at:
        raise ValueError("Welding stage already completed")
    return step


def accept_welding_job(
    db: Session, job: MesProductionJob, welding_ids: set[int], username: str
) -> None:
    step = _require_welding_step(job, welding_ids)
    if step.accepted_at:
        raise ValueError("Job already accepted")
    now = datetime.utcnow()
    log_value_change(
        db, username, "accept", "mes_job_route_step", step.id, "accepted_at", None, now.isoformat()
    )
    step.accepted_at = now
    job.updated_at = now


def start_welding_job(
    db: Session, job: MesProductionJob, welding_ids: set[int], username: str
) -> None:
    step = _require_welding_step(job, welding_ids)
    if not step.accepted_at:
        raise ValueError("Accept the job before starting work")
    if step.started_at:
        raise ValueError("Work already started")
    now = datetime.utcnow()
    log_value_change(
        db, username, "start", "mes_job_route_step", step.id, "started_at", None, now.isoformat()
    )
    step.started_at = now
    if job.status == "released":
        old_status = job.status
        job.status = "in_progress"
        log_value_change(
            db, username, "status", "mes_production_job", job.id, "status", old_status, job.status
        )
        if job.started_at is None:
            job.started_at = now
    job.updated_at = now


def _complete_welding_step(
    db: Session,
    job: MesProductionJob,
    step: MesJobRouteStep,
    username: str,
    *,
    auto: bool = False,
) -> None:
    if step.completed_at:
        return
    if job_welding_progress_pct(job) < 100.0:
        raise ValueError("Welding progress must reach 100% before completing")

    now = datetime.utcnow()
    old_completed_at = step.completed_at.isoformat() if step.completed_at else None
    step.completed_at = now
    step.completed_parts_count = max(
        int(step.completed_parts_count or 0),
        count_accepted_bom_lines(job),
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
            db, username, "status", "mes_production_job", job.id, "status", old_status, job.status
        )
    job.updated_at = now


def complete_welding_job(
    db: Session, job: MesProductionJob, welding_ids: set[int], username: str
) -> None:
    step = _require_welding_step(job, welding_ids)
    if not step.started_at:
        raise ValueError("Start work before completing")
    _complete_welding_step(db, job, step, username, auto=False)


def _validate_qty_field(
    line: MesJobBomLine, field: str, qty: float, allocated: float
) -> None:
    if qty < 0:
        raise ValueError(f"{field} cannot be negative ({line.part_number})")
    if allocated > 0 and qty > allocated:
        raise ValueError(f"{field} cannot exceed allocated ({line.part_number})")


def update_welding_quantities(
    db: Session,
    job: MesProductionJob,
    welding_ids: set[int],
    username: str,
    updates: list[dict],
) -> bool:
    step = _require_welding_step(job, welding_ids)
    if not step.started_at:
        raise ValueError("Start work before entering quantities")

    line_map = {line.id: line for line in (job.bom_lines or [])}
    now = datetime.utcnow()
    changed = False

    for item in updates:
        bom_line_id = int(item["bom_line_id"])
        line = line_map.get(bom_line_id)
        if not line:
            raise ValueError(f"BOM line {bom_line_id} not found on job")
        allocated = float(line.allocated_quantity or 0)

        fields = {
            "completed_quantity": item.get("completed_quantity"),
            "accepted_quantity": item.get("accepted_quantity"),
            "rejected_quantity": item.get("rejected_quantity"),
        }
        for field, raw in fields.items():
            if raw is None:
                continue
            qty = max(0.0, float(raw))
            _validate_qty_field(line, field, qty, allocated)
            old = float(getattr(line, field) or 0)
            if old == qty:
                continue
            log_value_change(
                db, username, "quantity", "mes_job_bom_line", line.id, field, old, qty
            )
            setattr(line, field, qty)
            changed = True

        completed = float(line.completed_quantity or 0)
        accepted = float(line.accepted_quantity or 0)
        rejected = float(line.rejected_quantity or 0)
        if accepted + rejected > completed + 0.0001:
            raise ValueError(
                f"Accepted + rejected cannot exceed completed ({line.part_number})"
            )

    if changed:
        job.updated_at = now
        step.completed_parts_count = count_accepted_bom_lines(job)

    auto_completed = False
    if job_welding_progress_pct(job) >= 100.0:
        _complete_welding_step(db, job, step, username, auto=True)
        auto_completed = True

    return auto_completed
