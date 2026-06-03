"""MES production job helpers (release snapshot, serialization)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from constants import MES_JOB_PRIORITIES, MES_JOB_STATUSES
from models import (
    MesBomLine,
    MesJobBomLine,
    MesJobRouteStep,
    MesProductionJob,
    MesProductionRoute,
    MesProductTemplate,
    MesRouteStep,
)
from services.mes_bom import active_bom_lines
from services.mes_routes import active_route_steps, active_routes


def generate_job_number(db: Session) -> str:
    prefix = datetime.utcnow().strftime("JOB%y%m%d")
    existing = (
        db.query(MesProductionJob)
        .filter(MesProductionJob.job_number.like(f"{prefix}-%"))
        .count()
    )
    return f"{prefix}-{existing + 1:04d}"


def normalize_job_number(value: str) -> str:
    return (value or "").strip().upper()


def get_default_route(template: MesProductTemplate) -> MesProductionRoute | None:
    routes = active_routes(template)
    if template.default_route_id:
        match = next((r for r in routes if r.id == template.default_route_id), None)
        if match:
            return match
    match = next((r for r in routes if r.is_default), None)
    return match or (routes[0] if routes else None)


def serialize_job_bom_line(line: MesJobBomLine) -> dict:
    return {
        "id": line.id,
        "job_id": line.job_id,
        "source_bom_line_id": line.source_bom_line_id,
        "part_id": line.part_id,
        "part_number": line.part_number,
        "part_name": line.part_name,
        "unit": line.unit,
        "allocated_quantity": float(line.allocated_quantity or 0),
        "completed_quantity": float(line.completed_quantity or 0),
        "accepted_quantity": float(line.accepted_quantity or 0),
        "rejected_quantity": float(line.rejected_quantity or 0),
        "notes": line.notes or "",
        "drawing_url": line.drawing_url,
        "sort_order": line.sort_order,
    }


def serialize_job_route_step(step: MesJobRouteStep) -> dict:
    return {
        "id": step.id,
        "job_id": step.job_id,
        "source_route_step_id": step.source_route_step_id,
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
        "is_required": bool(step.is_required),
    }


def serialize_job(job: MesProductionJob, *, include_snapshots: bool = True) -> dict:
    template = job.template
    bom_lines = sorted(job.bom_lines or [], key=lambda line: (line.sort_order, line.id))
    route_steps = sorted(job.route_steps or [], key=lambda step: (step.step_order, step.id))
    payload = {
        "id": job.id,
        "job_number": job.job_number,
        "customer_name": job.customer_name or "",
        "order_reference": job.order_reference or "",
        "template_id": job.template_id,
        "template_code": template.code if template else None,
        "template_name": template.name if template else None,
        "route_id": job.route_id,
        "route_name": job.route.name if job.route else None,
        "route_version": job.route.version if job.route else None,
        "quantity": float(job.quantity or 0),
        "priority": job.priority or "normal",
        "due_date": job.due_date,
        "status": job.status,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "created_by": job.created_by,
        "bom_line_count": len(bom_lines),
        "route_step_count": len(route_steps),
    }
    if include_snapshots:
        payload["bom_lines"] = [serialize_job_bom_line(line) for line in bom_lines]
        payload["route_steps"] = [serialize_job_route_step(step) for step in route_steps]
    return payload


def load_job(db: Session, job_id: int) -> MesProductionJob | None:
    return (
        db.query(MesProductionJob)
        .options(
            joinedload(MesProductionJob.template),
            joinedload(MesProductionJob.route),
            joinedload(MesProductionJob.bom_lines),
            joinedload(MesProductionJob.route_steps),
        )
        .filter(MesProductionJob.id == job_id)
        .first()
    )


def release_job_snapshot(db: Session, job: MesProductionJob) -> None:
    if job.status != "draft":
        raise ValueError("Only draft jobs can be released")

    template = (
        db.query(MesProductTemplate)
        .options(
            joinedload(MesProductTemplate.bom_lines).joinedload(MesBomLine.part),
            joinedload(MesProductTemplate.routes)
            .joinedload(MesProductionRoute.steps)
            .joinedload(MesRouteStep.stage),
        )
        .filter(
            MesProductTemplate.id == job.template_id,
            MesProductTemplate.deleted_at.is_(None),
        )
        .first()
    )
    if not template:
        raise ValueError("Product template not found")

    route = get_default_route(template)
    if not route:
        raise ValueError("Template has no production route")

    bom_lines = active_bom_lines(template)
    if not bom_lines:
        raise ValueError("Template BOM is empty")

    steps = active_route_steps(route)
    if not steps:
        raise ValueError("Template route has no steps")

    job.bom_lines.clear()
    job.route_steps.clear()

    qty = float(job.quantity or 1)
    for line in bom_lines:
        part = line.part
        db.add(
            MesJobBomLine(
                job_id=job.id,
                source_bom_line_id=line.id,
                part_id=line.part_id,
                part_number=part.part_number if part else f"PART-{line.part_id}",
                part_name=part.name if part else "Unknown",
                unit=line.unit or (part.unit if part else "dona"),
                allocated_quantity=float(line.required_quantity or 0) * qty,
                completed_quantity=0.0,
                accepted_quantity=0.0,
                rejected_quantity=0.0,
                notes=line.notes or "",
                drawing_url=line.drawing_url,
                sort_order=line.sort_order,
            )
        )

    for step in steps:
        stage = step.stage
        db.add(
            MesJobRouteStep(
                job_id=job.id,
                source_route_step_id=step.id,
                stage_id=step.stage_id,
                stage_name=stage.name if stage else f"Stage-{step.stage_id}",
                step_order=step.step_order,
                department=step.department or (stage.department if stage else None),
                responsible_role=step.responsible_role,
                estimated_minutes=step.estimated_minutes,
                required_parts_count=int(step.required_parts_count or 0),
                completed_parts_count=0,
                instructions=step.instructions or "",
                is_required=bool(step.is_required),
            )
        )

    job.route_id = route.id
    job.status = "released"
    job.updated_at = datetime.utcnow()

    db.flush()
    from services.material_consumption import sync_job_material_reservations

    sync_job_material_reservations(db, job)


def validate_status_transition(current: str, new_status: str) -> None:
    if new_status not in MES_JOB_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")
    if current == new_status:
        return

    allowed: dict[str, set[str]] = {
        "draft": {"cancelled"},
        "released": {"in_progress", "on_hold", "cancelled"},
        "in_progress": {"on_hold", "completed", "cancelled"},
        "on_hold": {"in_progress", "cancelled"},
        "completed": set(),
        "cancelled": set(),
    }
    if new_status not in allowed.get(current, set()):
        raise ValueError(f"Cannot transition from {current} to {new_status}")


def apply_status_change(job: MesProductionJob, new_status: str) -> None:
    validate_status_transition(job.status, new_status)
    now = datetime.utcnow()
    if new_status == "in_progress" and job.started_at is None:
        job.started_at = now
    if new_status == "completed":
        job.completed_at = now
    job.status = new_status
    job.updated_at = now


def validate_priority(value: str) -> str:
    priority = (value or "normal").strip().lower()
    if priority not in MES_JOB_PRIORITIES:
        raise ValueError(f"Invalid priority; allowed: {', '.join(MES_JOB_PRIORITIES)}")
    return priority
