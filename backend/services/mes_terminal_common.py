"""Shared MES shop-floor terminal helpers."""

from __future__ import annotations

from datetime import datetime

from models import MesJobBomLine, MesJobRouteStep, MesProductionJob

QUEUE_JOB_STATUSES = ("released", "in_progress")
PRIORITY_RANK = {"urgent": 0, "high": 1, "normal": 2, "low": 3}


def ordered_steps(job: MesProductionJob) -> list[MesJobRouteStep]:
    return sorted(job.route_steps or [], key=lambda step: (step.step_order, step.id))


def get_active_step(job: MesProductionJob) -> MesJobRouteStep | None:
    for step in ordered_steps(job):
        if step.is_required and step.completed_at is None:
            return step
    return None


def prior_steps_complete(job: MesProductionJob, step: MesJobRouteStep) -> bool:
    for prior in ordered_steps(job):
        if prior.step_order >= step.step_order:
            break
        if prior.is_required and prior.completed_at is None:
            return False
    return True


def terminal_step_state(step: MesJobRouteStep | None) -> str:
    if not step:
        return "missing"
    if step.completed_at:
        return "completed"
    if step.started_at:
        return "in_progress"
    if step.accepted_at:
        return "accepted"
    return "pending_accept"


def serialize_route_step(step: MesJobRouteStep | None) -> dict | None:
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
        "state": terminal_step_state(step),
    }


def sort_queue(items: list[dict]) -> list[dict]:
    items.sort(
        key=lambda item: (
            PRIORITY_RANK.get(item.get("priority") or "normal", 2),
            item.get("due_date") or datetime.max,
            item.get("created_at") or datetime.max,
        )
    )
    return items
