"""MES production monitor — active jobs, route timeline, dashboard."""

from __future__ import annotations

from datetime import datetime, time

from sqlalchemy.orm import Session, joinedload

from models import MesProductionJob
from services.mes_terminal_common import PRIORITY_RANK, get_active_step, ordered_steps

MONITOR_STAGES = [
    "Lazer",
    "Svarshik",
    "Kraska",
    "Nazorat",
    "Upakovka",
    "Sklad",
    "Yuklash",
]

ACTIVE_JOB_STATUSES = ("released", "in_progress", "on_hold")

# Map paint-prep steps into the Kraska monitor slot.
KRASKA_STAGE_NAMES = {"Kraska", "Tozalash", "Quritish"}


def _step_matches_monitor_stage(step, monitor_name: str) -> bool:
    name = step.stage_name or ""
    if monitor_name == "Kraska":
        return name in KRASKA_STAGE_NAMES or (step.department or "") == "Kraska"
    return name == monitor_name


def steps_for_monitor_stage(job: MesProductionJob, monitor_name: str):
    return [s for s in ordered_steps(job) if _step_matches_monitor_stage(s, monitor_name)]


def monitor_stage_status(job: MesProductionJob, monitor_name: str) -> str:
    steps = steps_for_monitor_stage(job, monitor_name)
    if not steps:
        return "waiting"

    required = [s for s in steps if s.is_required]
    check = required or steps
    if all(s.completed_at for s in check):
        return "completed"

    active = get_active_step(job)
    if active and any(s.id == active.id for s in steps):
        return "active"

    if active:
        monitor_orders = [s.step_order for s in steps]
        if active.step_order > max(monitor_orders):
            return "completed"

    return "waiting"


def build_route_timeline(job: MesProductionJob) -> list[dict]:
    timeline = []
    for stage_name in MONITOR_STAGES:
        steps = steps_for_monitor_stage(job, stage_name)
        timeline.append(
            {
                "stage": stage_name,
                "status": monitor_stage_status(job, stage_name),
                "step_count": len(steps),
            }
        )
    return timeline


def job_overall_progress_pct(job: MesProductionJob) -> float:
    steps = [s for s in ordered_steps(job) if s.is_required]
    if not steps:
        lines = [line for line in (job.bom_lines or []) if float(line.allocated_quantity or 0) > 0]
        if not lines:
            return 100.0 if job.status == "completed" else 0.0
        total_alloc = sum(float(line.allocated_quantity or 0) for line in lines)
        total_done = sum(float(line.accepted_quantity or 0) for line in lines)
        if total_alloc <= 0:
            return 0.0
        return min(100.0, round((total_done / total_alloc) * 100.0, 2))

    completed = sum(1 for s in steps if s.completed_at)
    return min(100.0, round((completed / len(steps)) * 100.0, 2))


def current_stage_name(job: MesProductionJob) -> str:
    active = get_active_step(job)
    if active:
        return active.stage_name or "—"
    if job.status == "completed":
        return "Completed"
    if job.status == "on_hold":
        return "On hold"
    return "—"


def is_job_delayed(job: MesProductionJob, now: datetime | None = None) -> bool:
    if job.status not in ACTIVE_JOB_STATUSES:
        return False
    if not job.due_date:
        return False
    ref = now or datetime.utcnow()
    return job.due_date < ref


def serialize_monitor_job(job: MesProductionJob) -> dict:
    return {
        "id": job.id,
        "job_number": job.job_number,
        "customer_name": job.customer_name or "",
        "order_reference": job.order_reference or "",
        "template_id": job.template_id,
        "template_code": job.template.code if job.template else None,
        "template_name": job.template.name if job.template else None,
        "product": job.template.name if job.template else None,
        "quantity": float(job.quantity or 0),
        "priority": job.priority or "normal",
        "due_date": job.due_date,
        "status": job.status,
        "current_stage": current_stage_name(job),
        "overall_progress_pct": job_overall_progress_pct(job),
        "route_timeline": build_route_timeline(job),
        "is_delayed": is_job_delayed(job),
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
    }


def _load_jobs_query(db: Session):
    return (
        db.query(MesProductionJob)
        .options(
            joinedload(MesProductionJob.template),
            joinedload(MesProductionJob.bom_lines),
            joinedload(MesProductionJob.route_steps),
        )
        .filter(MesProductionJob.status.in_(ACTIVE_JOB_STATUSES))
        .order_by(MesProductionJob.created_at.desc())
    )


def list_monitor_jobs(
    db: Session,
    *,
    stage: str = "",
    customer: str = "",
    priority: str = "",
) -> list[dict]:
    jobs = _load_jobs_query(db).all()
    items = [serialize_monitor_job(job) for job in jobs]

    if stage.strip():
        needle = stage.strip().lower()
        items = [
            j
            for j in items
            if j["current_stage"].lower() == needle
            or any(
                t["stage"].lower() == needle and t["status"] == "active"
                for t in j["route_timeline"]
            )
        ]

    if customer.strip():
        term = customer.strip().lower()
        items = [
            j
            for j in items
            if term in (j["customer_name"] or "").lower()
            or term in (j["order_reference"] or "").lower()
        ]

    if priority.strip():
        items = [j for j in items if j["priority"] == priority.strip().lower()]

    items.sort(
        key=lambda item: (
            PRIORITY_RANK.get(item.get("priority") or "normal", 2),
            item.get("due_date") or datetime.max,
            item.get("created_at") or datetime.max,
        )
    )
    return items


def monitor_dashboard(db: Session) -> dict:
    now = datetime.utcnow()
    today_start = datetime.combine(now.date(), time.min)

    active_jobs = (
        db.query(MesProductionJob)
        .options(joinedload(MesProductionJob.route_steps))
        .filter(MesProductionJob.status.in_(ACTIVE_JOB_STATUSES))
        .all()
    )
    in_progress = sum(1 for j in active_jobs if j.status == "in_progress")
    delayed = sum(1 for j in active_jobs if is_job_delayed(j, now))

    completed_today = (
        db.query(MesProductionJob)
        .filter(
            MesProductionJob.status == "completed",
            MesProductionJob.completed_at.isnot(None),
            MesProductionJob.completed_at >= today_start,
        )
        .count()
    )

    return {
        "active_jobs": len(active_jobs),
        "delayed_jobs": delayed,
        "completed_today": completed_today,
        "in_progress": in_progress,
        "monitor_stages": list(MONITOR_STAGES),
    }
