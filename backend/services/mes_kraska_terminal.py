"""Kraska (paint) shop-floor terminal."""

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
    sort_queue,
)

PAINT_DEPARTMENT = "Kraska"
PAINT_STAGE_NAMES = {"Kraska", "Tozalash", "Quritish"}


def get_paint_stages(db: Session) -> list[MesProductionStage]:
    return (
        db.query(MesProductionStage)
        .filter(
            MesProductionStage.is_active.is_(True),
            MesProductionStage.department == PAINT_DEPARTMENT,
        )
        .order_by(MesProductionStage.sort_order, MesProductionStage.name)
        .all()
    )


def paint_stage_ids(db: Session) -> set[int]:
    return {stage.id for stage in get_paint_stages(db)}


def get_current_paint_step(job: MesProductionJob, paint_ids: set[int]) -> MesJobRouteStep | None:
    active = get_active_step(job)
    if active and active.stage_id in paint_ids:
        return active
    return None


def find_paint_step(job: MesProductionJob, paint_ids: set[int]) -> MesJobRouteStep | None:
    current = get_current_paint_step(job, paint_ids)
    if current:
        return current
    return next((s for s in ordered_steps(job) if s.stage_id in paint_ids), None)


def job_in_paint_queue(job: MesProductionJob, paint_ids: set[int]) -> bool:
    if job.status not in QUEUE_JOB_STATUSES:
        return False
    active = get_active_step(job)
    if not active or active.stage_id not in paint_ids:
        return False
    return prior_steps_complete(job, active)


def kraska_step_state(step: MesJobRouteStep | None) -> str:
    if not step:
        return "missing"
    if step.completed_at:
        return "completed"
    if step.drying_at:
        return "drying"
    if step.started_at:
        return "in_progress"
    if step.accepted_at:
        return "accepted"
    return "pending_accept"


def serialize_kraska_step(step: MesJobRouteStep | None) -> dict | None:
    if not step:
        return None
    return {
        "id": step.id,
        "stage_id": step.stage_id,
        "stage_name": step.stage_name,
        "step_order": step.step_order,
        "department": step.department,
        "started_at": step.started_at,
        "accepted_at": step.accepted_at,
        "drying_at": step.drying_at,
        "completed_at": step.completed_at,
        "state": kraska_step_state(step),
    }


def serialize_paint_metadata(job: MesProductionJob) -> dict:
    return {
        "color_name": job.paint_color_name or "",
        "ral_code": job.paint_ral_code or "",
        "paint_type": job.paint_type or "",
        "batch_number": job.paint_batch_number or "",
    }


def bom_line_progress_pct(line: MesJobBomLine) -> float:
    allocated = float(line.allocated_quantity or 0)
    if allocated <= 0:
        return 100.0
    painted = float(line.painted_quantity or 0)
    return min(100.0, round((painted / allocated) * 100.0, 2))


def job_paint_progress_pct(job: MesProductionJob) -> float:
    lines = [line for line in (job.bom_lines or []) if float(line.allocated_quantity or 0) > 0]
    if not lines:
        return 0.0
    total_allocated = sum(float(line.allocated_quantity or 0) for line in lines)
    if total_allocated <= 0:
        return 0.0
    total_painted = sum(float(line.painted_quantity or 0) for line in lines)
    return min(100.0, round((total_painted / total_allocated) * 100.0, 2))


def count_painted_bom_lines(job: MesProductionJob) -> int:
    count = 0
    for line in job.bom_lines or []:
        allocated = float(line.allocated_quantity or 0)
        painted = float(line.painted_quantity or 0)
        if allocated <= 0 or painted >= allocated:
            count += 1
    return count


def serialize_bom_line_terminal(line: MesJobBomLine) -> dict:
    return {
        "id": line.id,
        "part_id": line.part_id,
        "part_number": line.part_number,
        "part_name": line.part_name,
        "unit": line.unit,
        "allocated_quantity": float(line.allocated_quantity or 0),
        "painted_quantity": float(line.painted_quantity or 0),
        "accepted_quantity": float(line.accepted_quantity or 0),
        "rejected_quantity": float(line.rejected_quantity or 0),
        "drawing_url": line.drawing_url,
        "notes": line.notes or "",
        "sort_order": line.sort_order,
        "progress_pct": bom_line_progress_pct(line),
        "is_paint_relevant": True,
    }


def serialize_terminal_job(
    job: MesProductionJob,
    paint_ids: set[int],
    *,
    include_bom: bool = True,
) -> dict:
    paint_step = find_paint_step(job, paint_ids)
    current = get_current_paint_step(job, paint_ids) or paint_step
    bom_lines = sorted(job.bom_lines or [], key=lambda line: (line.sort_order, line.id))
    paint_parts = [line for line in bom_lines if float(line.allocated_quantity or 0) > 0]
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
        "paint_step": serialize_kraska_step(current),
        "step_state": kraska_step_state(current),
        "paint_metadata": serialize_paint_metadata(job),
        "overall_progress_pct": job_paint_progress_pct(job),
        "bom_line_count": len(bom_lines),
        "paint_part_count": len(paint_parts),
    }
    if include_bom:
        payload["bom_lines"] = [serialize_bom_line_terminal(line) for line in bom_lines]
        payload["paint_parts"] = [serialize_bom_line_terminal(line) for line in paint_parts]
    return payload


def list_paint_queue(db: Session, paint_ids: set[int]) -> list[dict]:
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
        if not job_in_paint_queue(job, paint_ids):
            continue
        queue.append(serialize_terminal_job(job, paint_ids, include_bom=False))
    return sort_queue(queue)


def kraska_dashboard(db: Session, paint_ids: set[int]) -> dict:
    queue = list_paint_queue(db, paint_ids)
    waiting = sum(1 for j in queue if j.get("step_state") in ("pending_accept", "accepted"))
    active = sum(1 for j in queue if j.get("step_state") == "in_progress")
    drying = sum(1 for j in queue if j.get("step_state") == "drying")

    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    completed_today = (
        db.query(MesJobRouteStep)
        .filter(
            MesJobRouteStep.stage_id.in_(paint_ids),
            MesJobRouteStep.completed_at.isnot(None),
            MesJobRouteStep.completed_at >= today_start,
        )
        .count()
    )

    return {
        "waiting_jobs": waiting,
        "active_jobs": active,
        "drying_jobs": drying,
        "completed_today": completed_today,
    }


def _require_paint_step(job: MesProductionJob, paint_ids: set[int]) -> MesJobRouteStep:
    if job.status not in QUEUE_JOB_STATUSES:
        raise ValueError("Job is not active for terminal work")
    step = get_current_paint_step(job, paint_ids)
    if not step:
        raise ValueError("Job is not waiting at paint stage")
    if step.completed_at:
        raise ValueError("Paint stage already completed")
    return step


def accept_paint_job(db: Session, job: MesProductionJob, paint_ids: set[int], username: str) -> None:
    step = _require_paint_step(job, paint_ids)
    if step.accepted_at:
        raise ValueError("Job already accepted")
    now = datetime.utcnow()
    log_value_change(
        db, username, "accept", "mes_job_route_step", step.id, "accepted_at", None, now.isoformat()
    )
    step.accepted_at = now
    job.updated_at = now


def start_paint_job(db: Session, job: MesProductionJob, paint_ids: set[int], username: str) -> None:
    step = _require_paint_step(job, paint_ids)
    if not step.accepted_at:
        raise ValueError("Accept the job before starting work")
    if step.started_at:
        raise ValueError("Work already started")
    from services.material_auto_consumption import auto_consume_on_stage_start

    auto_consume_on_stage_start(db, job, "Kraska", username)
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


def send_to_drying(
    db: Session, job: MesProductionJob, paint_ids: set[int], username: str
) -> None:
    step = _require_paint_step(job, paint_ids)
    if not step.started_at:
        raise ValueError("Start work before sending to drying")
    if step.drying_at:
        raise ValueError("Already in drying")
    if job_paint_progress_pct(job) < 100.0:
        raise ValueError("Paint all parts before sending to drying")
    now = datetime.utcnow()
    log_value_change(
        db, username, "drying", "mes_job_route_step", step.id, "drying_at", None, now.isoformat()
    )
    step.drying_at = now
    job.updated_at = now


def _complete_paint_step(
    db: Session,
    job: MesProductionJob,
    step: MesJobRouteStep,
    username: str,
    *,
    auto: bool = False,
) -> None:
    if step.completed_at:
        return
    if job_paint_progress_pct(job) < 100.0:
        raise ValueError("Paint progress must reach 100% before completing")

    now = datetime.utcnow()
    if not step.drying_at:
        log_value_change(
            db,
            username,
            "auto_drying" if auto else "drying",
            "mes_job_route_step",
            step.id,
            "drying_at",
            None,
            now.isoformat(),
        )
        step.drying_at = now

    old_completed_at = step.completed_at.isoformat() if step.completed_at else None
    step.completed_at = now
    step.completed_parts_count = max(
        int(step.completed_parts_count or 0),
        count_painted_bom_lines(job),
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


def complete_paint_job(
    db: Session, job: MesProductionJob, paint_ids: set[int], username: str
) -> None:
    step = _require_paint_step(job, paint_ids)
    if not step.started_at:
        raise ValueError("Start work before completing")
    if not step.drying_at:
        raise ValueError("Send job to drying before completing")
    _complete_paint_step(db, job, step, username, auto=False)


def update_paint_metadata(
    db: Session,
    job: MesProductionJob,
    username: str,
    *,
    color_name: str | None = None,
    ral_code: str | None = None,
    paint_type: str | None = None,
    batch_number: str | None = None,
) -> None:
    fields = {
        "paint_color_name": color_name,
        "paint_ral_code": ral_code,
        "paint_type": paint_type,
        "paint_batch_number": batch_number,
    }
    now = datetime.utcnow()
    for field, new_val in fields.items():
        if new_val is None:
            continue
        old = getattr(job, field) or ""
        new = (new_val or "").strip()
        if old == new:
            continue
        log_value_change(db, username, "paint_meta", "mes_production_job", job.id, field, old, new)
        setattr(job, field, new)
    job.updated_at = now


def update_paint_quantities(
    db: Session,
    job: MesProductionJob,
    paint_ids: set[int],
    username: str,
    updates: list[dict],
) -> bool:
    step = _require_paint_step(job, paint_ids)
    if not step.started_at:
        raise ValueError("Start work before entering quantities")

    line_map = {line.id: line for line in (job.bom_lines or [])}
    now = datetime.utcnow()
    changed = False

    qty_fields = ("painted_quantity", "accepted_quantity", "rejected_quantity")
    for item in updates:
        bom_line_id = int(item["bom_line_id"])
        line = line_map.get(bom_line_id)
        if not line:
            raise ValueError(f"BOM line {bom_line_id} not found on job")
        allocated = float(line.allocated_quantity or 0)

        for field in qty_fields:
            if field not in item or item[field] is None:
                continue
            qty = max(0.0, float(item[field]))
            if allocated > 0 and qty > allocated:
                raise ValueError(f"{field} cannot exceed allocated ({line.part_number})")
            old = float(getattr(line, field) or 0)
            if old == qty:
                continue
            log_value_change(
                db, username, "quantity", "mes_job_bom_line", line.id, field, old, qty
            )
            setattr(line, field, qty)
            changed = True

        painted = float(line.painted_quantity or 0)
        accepted = float(line.accepted_quantity or 0)
        rejected = float(line.rejected_quantity or 0)
        if accepted + rejected > painted + 0.0001:
            raise ValueError(
                f"Accepted + rejected cannot exceed painted ({line.part_number})"
            )

    if changed:
        job.updated_at = now
        step.completed_parts_count = count_painted_bom_lines(job)

    auto_completed = False
    if job_paint_progress_pct(job) >= 100.0:
        _complete_paint_step(db, job, step, username, auto=True)
        auto_completed = True

    return auto_completed
