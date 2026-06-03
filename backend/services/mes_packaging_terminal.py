"""Upakovka (packaging) shop-floor terminal."""

from __future__ import annotations

from datetime import datetime, time

from sqlalchemy.orm import Session, joinedload

from models import MesJobPackage, MesJobRouteStep, MesProductionJob, MesProductionStage
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

PACKAGING_DEPARTMENT = "Upakovka"
WAREHOUSE_STAGE_NAME = "Sklad"


def get_packaging_stages(db: Session) -> list[MesProductionStage]:
    return (
        db.query(MesProductionStage)
        .filter(
            MesProductionStage.is_active.is_(True),
            MesProductionStage.department == PACKAGING_DEPARTMENT,
        )
        .order_by(MesProductionStage.sort_order, MesProductionStage.name)
        .all()
    )


def packaging_stage_ids(db: Session) -> set[int]:
    return {stage.id for stage in get_packaging_stages(db)}


def get_current_packaging_step(
    job: MesProductionJob, packaging_ids: set[int]
) -> MesJobRouteStep | None:
    active = get_active_step(job)
    if active and active.stage_id in packaging_ids:
        return active
    return None


def find_packaging_step(
    job: MesProductionJob, packaging_ids: set[int]
) -> MesJobRouteStep | None:
    current = get_current_packaging_step(job, packaging_ids)
    if current:
        return current
    return next((s for s in ordered_steps(job) if s.stage_id in packaging_ids), None)


def job_in_packaging_queue(job: MesProductionJob, packaging_ids: set[int]) -> bool:
    if job.status not in QUEUE_JOB_STATUSES:
        return False
    active = get_active_step(job)
    if not active or active.stage_id not in packaging_ids:
        return False
    return prior_steps_complete(job, active)


def active_packages(job: MesProductionJob) -> list[MesJobPackage]:
    return [p for p in (job.packages or []) if p.status != "cancelled"]


def package_totals(job: MesProductionJob) -> dict:
    packages = active_packages(job)
    return {
        "packages_created": len(packages),
        "total_net_weight_kg": round(sum(float(p.net_weight_kg or 0) for p in packages), 3),
        "total_gross_weight_kg": round(sum(float(p.gross_weight_kg or 0) for p in packages), 3),
    }


def packaging_progress_pct(job: MesProductionJob) -> float:
    target = int(job.package_count or 0)
    if target <= 0:
        count = len(active_packages(job))
        return 100.0 if count > 0 else 0.0
    current = len(active_packages(job))
    return min(100.0, round((current / target) * 100.0, 2))


def serialize_package(pkg: MesJobPackage) -> dict:
    return {
        "id": pkg.id,
        "job_id": pkg.job_id,
        "package_number": pkg.package_number,
        "package_type": pkg.package_type or "",
        "net_weight_kg": float(pkg.net_weight_kg or 0),
        "gross_weight_kg": float(pkg.gross_weight_kg or 0),
        "status": pkg.status,
        "created_at": pkg.created_at,
    }


def serialize_terminal_job(
    job: MesProductionJob,
    packaging_ids: set[int],
    *,
    include_packages: bool = True,
) -> dict:
    packaging_step = find_packaging_step(job, packaging_ids)
    current_step = get_current_packaging_step(job, packaging_ids) or packaging_step
    totals = package_totals(job)
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
        "packaging_step": serialize_route_step(current_step),
        "step_state": terminal_step_state(current_step),
        "overall_progress_pct": packaging_progress_pct(job),
        "package_type": job.package_type or "",
        "package_count": int(job.package_count or 0),
        "net_weight_kg": float(job.packaging_net_weight_kg or 0),
        "gross_weight_kg": float(job.packaging_gross_weight_kg or 0),
        "notes": job.packaging_notes or "",
        **totals,
    }
    if include_packages:
        packages = sorted(active_packages(job), key=lambda p: p.package_number)
        payload["packages"] = [serialize_package(p) for p in packages]
    return payload


def list_packaging_queue(db: Session, packaging_ids: set[int]) -> list[dict]:
    jobs = (
        db.query(MesProductionJob)
        .options(
            joinedload(MesProductionJob.template),
            joinedload(MesProductionJob.packages),
            joinedload(MesProductionJob.route_steps),
        )
        .filter(MesProductionJob.status.in_(QUEUE_JOB_STATUSES))
        .all()
    )
    queue = []
    for job in jobs:
        if not job_in_packaging_queue(job, packaging_ids):
            continue
        queue.append(serialize_terminal_job(job, packaging_ids, include_packages=False))
    return sort_queue(queue)


def packaging_dashboard(db: Session, packaging_ids: set[int]) -> dict:
    queue = list_packaging_queue(db, packaging_ids)
    active = sum(1 for job in queue if job.get("step_state") == "in_progress")
    waiting = sum(1 for job in queue if job.get("step_state") in ("pending_accept", "accepted"))

    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    completed_today = (
        db.query(MesJobRouteStep)
        .filter(
            MesJobRouteStep.stage_id.in_(packaging_ids),
            MesJobRouteStep.completed_at.isnot(None),
            MesJobRouteStep.completed_at >= today_start,
        )
        .count()
    )

    total_packages_today = (
        db.query(MesJobPackage)
        .filter(MesJobPackage.created_at >= today_start, MesJobPackage.status != "cancelled")
        .count()
    )

    return {
        "waiting_jobs": waiting,
        "active_jobs": active,
        "completed_today": completed_today,
        "total_packages_today": total_packages_today,
    }


def _require_packaging_step(job: MesProductionJob, packaging_ids: set[int]) -> MesJobRouteStep:
    if job.status not in QUEUE_JOB_STATUSES:
        raise ValueError("Job is not active for terminal work")
    step = get_current_packaging_step(job, packaging_ids)
    if not step:
        raise ValueError("Job is not waiting at packaging stage")
    if step.completed_at:
        raise ValueError("Packaging stage already completed")
    return step


def accept_packaging_job(
    db: Session, job: MesProductionJob, packaging_ids: set[int], username: str
) -> None:
    step = _require_packaging_step(job, packaging_ids)
    if step.accepted_at:
        raise ValueError("Job already accepted")
    now = datetime.utcnow()
    log_value_change(
        db, username, "accept", "mes_job_route_step", step.id, "accepted_at", None, now.isoformat()
    )
    step.accepted_at = now
    job.updated_at = now


def start_packaging_job(
    db: Session, job: MesProductionJob, packaging_ids: set[int], username: str
) -> None:
    step = _require_packaging_step(job, packaging_ids)
    if not step.accepted_at:
        raise ValueError("Accept the job before starting packaging")
    if step.started_at:
        raise ValueError("Packaging already started")
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


def _package_number(job: MesProductionJob, index: int) -> str:
    return f"PACK-{job.job_number}-{index:03d}"


def sync_package_records(
    db: Session,
    job: MesProductionJob,
    username: str,
    *,
    package_type: str,
    package_count: int,
    net_weight_kg: float,
    gross_weight_kg: float,
) -> None:
    if package_count < 0:
        raise ValueError("Package count cannot be negative")

    existing = sorted(active_packages(job), key=lambda p: p.package_number)
    per_net = round(net_weight_kg / package_count, 3) if package_count > 0 else 0.0
    per_gross = round(gross_weight_kg / package_count, 3) if package_count > 0 else 0.0
    now = datetime.utcnow()

    for i in range(1, package_count + 1):
        pkg_num = _package_number(job, i)
        if i <= len(existing):
            pkg = existing[i - 1]
            if pkg.package_number != pkg_num:
                old = pkg.package_number
                pkg.package_number = pkg_num
                log_value_change(
                    db,
                    username,
                    "update",
                    "mes_job_package",
                    pkg.id,
                    "package_number",
                    old,
                    pkg_num,
                )
        else:
            pkg = MesJobPackage(
                job_id=job.id,
                package_number=pkg_num,
                package_type=package_type,
                net_weight_kg=per_net,
                gross_weight_kg=per_gross,
                status="pending",
                created_at=now,
            )
            db.add(pkg)
            db.flush()
            log_value_change(
                db,
                username,
                "create",
                "mes_job_package",
                pkg.id,
                "package_number",
                None,
                pkg_num,
            )
            existing.append(pkg)

        pkg = existing[i - 1]
        if (pkg.package_type or "") != package_type:
            log_value_change(
                db,
                username,
                "update",
                "mes_job_package",
                pkg.id,
                "package_type",
                pkg.package_type or "",
                package_type,
            )
            pkg.package_type = package_type
        if float(pkg.net_weight_kg or 0) != per_net:
            log_value_change(
                db,
                username,
                "update",
                "mes_job_package",
                pkg.id,
                "net_weight_kg",
                float(pkg.net_weight_kg or 0),
                per_net,
            )
            pkg.net_weight_kg = per_net
        if float(pkg.gross_weight_kg or 0) != per_gross:
            log_value_change(
                db,
                username,
                "update",
                "mes_job_package",
                pkg.id,
                "gross_weight_kg",
                float(pkg.gross_weight_kg or 0),
                per_gross,
            )
            pkg.gross_weight_kg = per_gross

    if len(existing) > package_count:
        for pkg in existing[package_count:]:
            if pkg.status == "cancelled":
                continue
            old = pkg.status
            pkg.status = "cancelled"
            log_value_change(
                db,
                username,
                "cancel",
                "mes_job_package",
                pkg.id,
                "status",
                old,
                "cancelled",
            )


def update_packaging_data(
    db: Session,
    job: MesProductionJob,
    packaging_ids: set[int],
    username: str,
    *,
    package_type: str | None = None,
    package_count: int | None = None,
    net_weight_kg: float | None = None,
    gross_weight_kg: float | None = None,
    notes: str | None = None,
) -> None:
    step = _require_packaging_step(job, packaging_ids)
    if not step.started_at:
        raise ValueError("Start packaging before entering data")

    now = datetime.utcnow()
    fields = {
        "package_type": package_type,
        "package_count": package_count,
        "packaging_net_weight_kg": net_weight_kg,
        "packaging_gross_weight_kg": gross_weight_kg,
        "packaging_notes": notes,
    }
    for field, new_val in fields.items():
        if new_val is None:
            continue
        if field == "package_count":
            new = int(new_val)
            old = int(getattr(job, field) or 0)
        elif field in ("packaging_net_weight_kg", "packaging_gross_weight_kg"):
            new = max(0.0, float(new_val))
            old = float(getattr(job, field) or 0)
        elif field == "packaging_notes":
            new = (new_val or "").strip()
            old = getattr(job, field) or ""
        else:
            new = (new_val or "").strip()
            old = getattr(job, field) or ""
        if old == new:
            continue
        log_value_change(db, username, "packaging", "mes_production_job", job.id, field, old, new)
        setattr(job, field, new)

    count = int(job.package_count or 0)
    if count > 0:
        sync_package_records(
            db,
            job,
            username,
            package_type=job.package_type or "",
            package_count=count,
            net_weight_kg=float(job.packaging_net_weight_kg or 0),
            gross_weight_kg=float(job.packaging_gross_weight_kg or 0),
        )
    job.updated_at = now


def _next_step_after_packaging(job: MesProductionJob) -> MesJobRouteStep | None:
    packaging_step = None
    for step in ordered_steps(job):
        if step.stage_name == WAREHOUSE_STAGE_NAME and step.is_required:
            return step
        if step.department == PACKAGING_DEPARTMENT or step.stage_name == "Upakovka":
            packaging_step = step
    return None


def _complete_packaging_step(
    db: Session,
    job: MesProductionJob,
    step: MesJobRouteStep,
    username: str,
    *,
    auto: bool = False,
) -> None:
    if step.completed_at:
        return

    count = int(job.package_count or 0)
    packages = active_packages(job)
    if count <= 0:
        raise ValueError("Set package count before completing")
    if len(packages) < count:
        raise ValueError("Generate all package labels before completing")

    now = datetime.utcnow()
    for pkg in packages:
        if pkg.status != "packed":
            old = pkg.status
            pkg.status = "packed"
            log_value_change(
                db,
                username,
                "pack",
                "mes_job_package",
                pkg.id,
                "status",
                old,
                "packed",
            )

    old_completed_at = step.completed_at.isoformat() if step.completed_at else None
    step.completed_at = now
    step.completed_parts_count = len(packages)
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

    warehouse_step = _next_step_after_packaging(job)
    if warehouse_step:
        log_value_change(
            db,
            username,
            "warehouse_transition",
            "mes_production_job",
            job.id,
            "active_stage",
            step.stage_name,
            warehouse_step.stage_name,
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


def complete_packaging_job(
    db: Session, job: MesProductionJob, packaging_ids: set[int], username: str
) -> None:
    step = _require_packaging_step(job, packaging_ids)
    if not step.started_at:
        raise ValueError("Start packaging before completing")
    _complete_packaging_step(db, job, step, username, auto=False)


def load_packaging_job(db: Session, job_id: int) -> MesProductionJob | None:
    return (
        db.query(MesProductionJob)
        .options(
            joinedload(MesProductionJob.template),
            joinedload(MesProductionJob.packages),
            joinedload(MesProductionJob.route_steps),
        )
        .filter(MesProductionJob.id == job_id)
        .first()
    )
