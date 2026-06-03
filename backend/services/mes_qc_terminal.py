"""QC (Nazorat / Tekshiruv) shop-floor terminal."""

from __future__ import annotations

from datetime import datetime, time

from sqlalchemy.orm import Session, joinedload

from models import (
    MesJobBomLine,
    MesJobRework,
    MesJobRouteStep,
    MesProductionJob,
    MesProductionStage,
    MesQcRejectionReason,
)
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

QC_DEPARTMENT = "Tekshiruv"
QC_STAGE_NAMES = {"Nazorat"}


def get_qc_stages(db: Session) -> list[MesProductionStage]:
    return (
        db.query(MesProductionStage)
        .filter(
            MesProductionStage.is_active.is_(True),
            MesProductionStage.department == QC_DEPARTMENT,
        )
        .order_by(MesProductionStage.sort_order, MesProductionStage.name)
        .all()
    )


def qc_stage_ids(db: Session) -> set[int]:
    return {stage.id for stage in get_qc_stages(db)}


def get_current_qc_step(job: MesProductionJob, qc_ids: set[int]) -> MesJobRouteStep | None:
    active = get_active_step(job)
    if active and active.stage_id in qc_ids:
        return active
    return None


def find_qc_step(job: MesProductionJob, qc_ids: set[int]) -> MesJobRouteStep | None:
    current = get_current_qc_step(job, qc_ids)
    if current:
        return current
    return next((s for s in ordered_steps(job) if s.stage_id in qc_ids), None)


def job_in_qc_queue(job: MesProductionJob, qc_ids: set[int]) -> bool:
    if job.status not in QUEUE_JOB_STATUSES:
        return False
    active = get_active_step(job)
    if not active or active.stage_id not in qc_ids:
        return False
    return prior_steps_complete(job, active)


def line_disposition_total(line: MesJobBomLine) -> float:
    return (
        float(line.accepted_quantity or 0)
        + float(line.rejected_quantity or 0)
        + float(line.rework_quantity or 0)
    )


def bom_line_progress_pct(line: MesJobBomLine) -> float:
    allocated = float(line.allocated_quantity or 0)
    if allocated <= 0:
        return 100.0
    inspected = line_disposition_total(line)
    return min(100.0, round((inspected / allocated) * 100.0, 2))


def job_qc_progress_pct(job: MesProductionJob) -> float:
    lines = [line for line in (job.bom_lines or []) if float(line.allocated_quantity or 0) > 0]
    if not lines:
        return 0.0
    total_allocated = sum(float(line.allocated_quantity or 0) for line in lines)
    if total_allocated <= 0:
        return 0.0
    total_inspected = sum(line_disposition_total(line) for line in lines)
    return min(100.0, round((total_inspected / total_allocated) * 100.0, 2))


def count_inspected_bom_lines(job: MesProductionJob) -> int:
    count = 0
    for line in job.bom_lines or []:
        allocated = float(line.allocated_quantity or 0)
        if allocated <= 0 or line_disposition_total(line) >= allocated:
            count += 1
    return count


def serialize_rejection_reason(reason: MesQcRejectionReason) -> dict:
    return {
        "id": reason.id,
        "name": reason.name,
        "sort_order": reason.sort_order,
        "is_active": bool(reason.is_active),
    }


def serialize_rework(record: MesJobRework) -> dict:
    return {
        "id": record.id,
        "job_id": record.job_id,
        "bom_line_id": record.bom_line_id,
        "part_number": record.bom_line.part_number if record.bom_line else "",
        "part_name": record.bom_line.part_name if record.bom_line else "",
        "rejection_reason_id": record.rejection_reason_id,
        "rejection_reason_name": record.rejection_reason.name if record.rejection_reason else "",
        "quantity": float(record.quantity or 0),
        "status": record.status,
        "notes": record.notes or "",
        "created_by": record.created_by,
        "created_at": record.created_at,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "completed_by": record.completed_by,
    }


def serialize_bom_line_terminal(line: MesJobBomLine) -> dict:
    allocated = float(line.allocated_quantity or 0)
    return {
        "id": line.id,
        "part_id": line.part_id,
        "part_number": line.part_number,
        "part_name": line.part_name,
        "unit": line.unit,
        "allocated_quantity": allocated,
        "accepted_quantity": float(line.accepted_quantity or 0),
        "rejected_quantity": float(line.rejected_quantity or 0),
        "rework_quantity": float(line.rework_quantity or 0),
        "drawing_url": line.drawing_url,
        "notes": line.notes or "",
        "sort_order": line.sort_order,
        "progress_pct": bom_line_progress_pct(line),
        "is_qc_relevant": True,
    }


def serialize_terminal_job(
    job: MesProductionJob,
    qc_ids: set[int],
    *,
    include_bom: bool = True,
    rework_records: list[MesJobRework] | None = None,
) -> dict:
    qc_step = find_qc_step(job, qc_ids)
    current_step = get_current_qc_step(job, qc_ids) or qc_step
    bom_lines = sorted(job.bom_lines or [], key=lambda line: (line.sort_order, line.id))
    qc_parts = [line for line in bom_lines if float(line.allocated_quantity or 0) > 0]
    open_rework = [
        r for r in (rework_records or []) if r.status in ("pending", "in_progress")
    ]
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
        "qc_step": serialize_route_step(current_step),
        "step_state": terminal_step_state(current_step),
        "overall_progress_pct": job_qc_progress_pct(job),
        "bom_line_count": len(bom_lines),
        "qc_part_count": len(qc_parts),
        "open_rework_count": len(open_rework),
    }
    if include_bom:
        payload["bom_lines"] = [serialize_bom_line_terminal(line) for line in bom_lines]
        payload["qc_parts"] = [serialize_bom_line_terminal(line) for line in qc_parts]
    if rework_records is not None:
        payload["rework_records"] = [serialize_rework(r) for r in rework_records]
    return payload


def list_qc_queue(db: Session, qc_ids: set[int]) -> list[dict]:
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
        if not job_in_qc_queue(job, qc_ids):
            continue
        open_rework = (
            db.query(MesJobRework)
            .filter(
                MesJobRework.job_id == job.id,
                MesJobRework.status.in_(("pending", "in_progress")),
            )
            .count()
        )
        item = serialize_terminal_job(job, qc_ids, include_bom=False)
        item["open_rework_count"] = open_rework
        queue.append(item)
    return sort_queue(queue)


def list_rework_queue(db: Session) -> list[dict]:
    records = (
        db.query(MesJobRework)
        .options(
            joinedload(MesJobRework.job).joinedload(MesProductionJob.template),
            joinedload(MesJobRework.bom_line),
            joinedload(MesJobRework.rejection_reason),
        )
        .filter(MesJobRework.status.in_(("pending", "in_progress")))
        .order_by(MesJobRework.created_at.desc())
        .all()
    )
    return [serialize_rework(r) for r in records]


def qc_dashboard(db: Session, qc_ids: set[int]) -> dict:
    queue = list_qc_queue(db, qc_ids)
    active = sum(1 for job in queue if job.get("step_state") == "in_progress")
    waiting = sum(1 for job in queue if job.get("step_state") in ("pending_accept", "accepted"))

    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    completed_today = (
        db.query(MesJobRouteStep)
        .filter(
            MesJobRouteStep.stage_id.in_(qc_ids),
            MesJobRouteStep.completed_at.isnot(None),
            MesJobRouteStep.completed_at >= today_start,
        )
        .count()
    )

    rework_jobs = (
        db.query(MesJobRework.job_id)
        .filter(MesJobRework.status.in_(("pending", "in_progress")))
        .distinct()
        .count()
    )

    return {
        "active_inspections": active,
        "waiting_jobs": waiting,
        "rework_jobs": rework_jobs,
        "completed_today": completed_today,
    }


def _require_qc_step(job: MesProductionJob, qc_ids: set[int]) -> MesJobRouteStep:
    if job.status not in QUEUE_JOB_STATUSES:
        raise ValueError("Job is not active for terminal work")
    step = get_current_qc_step(job, qc_ids)
    if not step:
        raise ValueError("Job is not waiting at QC stage")
    if step.completed_at:
        raise ValueError("QC stage already completed")
    return step


def accept_qc_job(db: Session, job: MesProductionJob, qc_ids: set[int], username: str) -> None:
    step = _require_qc_step(job, qc_ids)
    if step.accepted_at:
        raise ValueError("Inspection already accepted")
    now = datetime.utcnow()
    log_value_change(
        db, username, "accept", "mes_job_route_step", step.id, "accepted_at", None, now.isoformat()
    )
    step.accepted_at = now
    job.updated_at = now


def start_qc_job(db: Session, job: MesProductionJob, qc_ids: set[int], username: str) -> None:
    step = _require_qc_step(job, qc_ids)
    if not step.accepted_at:
        raise ValueError("Accept inspection before starting")
    if step.started_at:
        raise ValueError("Inspection already started")
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


def _complete_qc_step(
    db: Session,
    job: MesProductionJob,
    step: MesJobRouteStep,
    username: str,
    *,
    auto: bool = False,
) -> None:
    if step.completed_at:
        return
    if job_qc_progress_pct(job) < 100.0:
        raise ValueError("Inspection progress must reach 100% before completing")

    open_rework = (
        db.query(MesJobRework)
        .filter(
            MesJobRework.job_id == job.id,
            MesJobRework.status.in_(("pending", "in_progress")),
        )
        .count()
    )
    if open_rework:
        raise ValueError("Complete or resolve open rework records before finishing inspection")

    now = datetime.utcnow()
    old_completed_at = step.completed_at.isoformat() if step.completed_at else None
    step.completed_at = now
    step.completed_parts_count = max(
        int(step.completed_parts_count or 0),
        count_inspected_bom_lines(job),
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


def complete_qc_job(
    db: Session, job: MesProductionJob, qc_ids: set[int], username: str
) -> None:
    step = _require_qc_step(job, qc_ids)
    if not step.started_at:
        raise ValueError("Start inspection before completing")
    _complete_qc_step(db, job, step, username, auto=False)


def _validate_qty_field(
    line: MesJobBomLine, field: str, qty: float, allocated: float
) -> None:
    if qty < 0:
        raise ValueError(f"{field} cannot be negative ({line.part_number})")
    if allocated > 0 and qty > allocated:
        raise ValueError(f"{field} cannot exceed allocated ({line.part_number})")


def _validate_disposition(line: MesJobBomLine) -> None:
    allocated = float(line.allocated_quantity or 0)
    total = line_disposition_total(line)
    if total > allocated + 0.0001:
        raise ValueError(
            f"Accepted + rejected + rework cannot exceed allocated ({line.part_number})"
        )


def update_qc_quantities(
    db: Session,
    job: MesProductionJob,
    qc_ids: set[int],
    username: str,
    updates: list[dict],
) -> bool:
    step = _require_qc_step(job, qc_ids)
    if not step.started_at:
        raise ValueError("Start inspection before entering quantities")

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
            "accepted_quantity": item.get("accepted_quantity"),
            "rejected_quantity": item.get("rejected_quantity"),
            "rework_quantity": item.get("rework_quantity"),
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

        _validate_disposition(line)

    if changed:
        job.updated_at = now
        step.completed_parts_count = count_inspected_bom_lines(job)

    auto_completed = False
    if job_qc_progress_pct(job) >= 100.0:
        open_rework = (
            db.query(MesJobRework)
            .filter(
                MesJobRework.job_id == job.id,
                MesJobRework.status.in_(("pending", "in_progress")),
            )
            .count()
        )
        if not open_rework:
            _complete_qc_step(db, job, step, username, auto=True)
            auto_completed = True

    return auto_completed


def create_rework_record(
    db: Session,
    job: MesProductionJob,
    qc_ids: set[int],
    username: str,
    *,
    bom_line_id: int,
    quantity: float,
    rejection_reason_id: int | None = None,
    notes: str = "",
) -> MesJobRework:
    step = _require_qc_step(job, qc_ids)
    if not step.started_at:
        raise ValueError("Start inspection before creating rework")

    line_map = {line.id: line for line in (job.bom_lines or [])}
    line = line_map.get(bom_line_id)
    if not line:
        raise ValueError(f"BOM line {bom_line_id} not found on job")

    qty = max(0.0, float(quantity))
    if qty <= 0:
        raise ValueError("Rework quantity must be positive")

    allocated = float(line.allocated_quantity or 0)
    old_rework = float(line.rework_quantity or 0)
    new_rework = old_rework + qty
    _validate_qty_field(line, "rework_quantity", new_rework, allocated)

    if rejection_reason_id:
        reason = (
            db.query(MesQcRejectionReason)
            .filter(
                MesQcRejectionReason.id == rejection_reason_id,
                MesQcRejectionReason.is_active.is_(True),
            )
            .first()
        )
        if not reason:
            raise ValueError("Rejection reason not found")

    line.accepted_quantity = float(line.accepted_quantity or 0)
    line.rejected_quantity = float(line.rejected_quantity or 0)
    line.rework_quantity = new_rework
    _validate_disposition(line)

    now = datetime.utcnow()
    log_value_change(
        db, username, "quantity", "mes_job_bom_line", line.id, "rework_quantity", old_rework, new_rework
    )

    record = MesJobRework(
        job_id=job.id,
        bom_line_id=line.id,
        rejection_reason_id=rejection_reason_id,
        quantity=qty,
        status="pending",
        notes=(notes or "").strip(),
        created_by=username,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    job.updated_at = now
    db.flush()
    log_value_change(
        db,
        username,
        "create",
        "mes_job_rework",
        record.id,
        "status",
        None,
        record.status,
    )
    return record


def start_rework(db: Session, record: MesJobRework, username: str) -> None:
    if record.status != "pending":
        raise ValueError("Rework is not pending")
    now = datetime.utcnow()
    log_value_change(
        db, username, "start", "mes_job_rework", record.id, "status", record.status, "in_progress"
    )
    record.status = "in_progress"
    record.started_at = now
    record.updated_at = now


def complete_rework(db: Session, record: MesJobRework, username: str) -> None:
    if record.status not in ("pending", "in_progress"):
        raise ValueError("Rework is already completed")
    now = datetime.utcnow()
    old = record.status
    record.status = "completed"
    record.completed_at = now
    record.completed_by = username
    record.updated_at = now
    if not record.started_at:
        record.started_at = now
    log_value_change(
        db, username, "complete", "mes_job_rework", record.id, "status", old, record.status
    )


def load_job_reworks(db: Session, job_id: int) -> list[MesJobRework]:
    return (
        db.query(MesJobRework)
        .options(
            joinedload(MesJobRework.bom_line),
            joinedload(MesJobRework.rejection_reason),
        )
        .filter(MesJobRework.job_id == job_id)
        .order_by(MesJobRework.created_at.desc())
        .all()
    )


# --- Admin rejection reasons ---

DEFAULT_QC_REJECTION_REASONS = [
    "Geometriya xatoligi",
    "Bo'yash nuqsoni",
    "Payvandlash nuqsoni",
    "O'lcham mos kelmasligi",
    "Boshqa",
]


def seed_qc_rejection_reasons(db: Session) -> None:
    for order, name in enumerate(DEFAULT_QC_REJECTION_REASONS):
        existing = (
            db.query(MesQcRejectionReason).filter(MesQcRejectionReason.name == name).first()
        )
        if not existing:
            db.add(
                MesQcRejectionReason(
                    name=name,
                    sort_order=order,
                    is_active=True,
                )
            )
    db.commit()


def list_rejection_reasons(db: Session, *, include_inactive: bool = False) -> list[dict]:
    query = db.query(MesQcRejectionReason).order_by(
        MesQcRejectionReason.sort_order, MesQcRejectionReason.name
    )
    if not include_inactive:
        query = query.filter(MesQcRejectionReason.is_active.is_(True))
    return [serialize_rejection_reason(r) for r in query.all()]


def create_rejection_reason(db: Session, username: str, name: str, sort_order: int = 0) -> dict:
    clean = (name or "").strip()
    if not clean:
        raise ValueError("Name is required")
    existing = (
        db.query(MesQcRejectionReason)
        .filter(MesQcRejectionReason.name == clean, MesQcRejectionReason.is_active.is_(True))
        .first()
    )
    if existing:
        raise ValueError("Rejection reason already exists")
    reason = MesQcRejectionReason(name=clean, sort_order=sort_order, is_active=True)
    db.add(reason)
    db.flush()
    log_value_change(db, username, "create", "mes_qc_rejection_reason", reason.id, "name", None, clean)
    return serialize_rejection_reason(reason)


def update_rejection_reason(
    db: Session,
    reason: MesQcRejectionReason,
    username: str,
    *,
    name: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
) -> dict:
    if name is not None:
        clean = name.strip()
        if not clean:
            raise ValueError("Name is required")
        if clean != reason.name:
            dup = (
                db.query(MesQcRejectionReason)
                .filter(
                    MesQcRejectionReason.name == clean,
                    MesQcRejectionReason.id != reason.id,
                    MesQcRejectionReason.is_active.is_(True),
                )
                .first()
            )
            if dup:
                raise ValueError("Rejection reason already exists")
            log_value_change(
                db, username, "update", "mes_qc_rejection_reason", reason.id, "name", reason.name, clean
            )
            reason.name = clean
    if sort_order is not None:
        reason.sort_order = sort_order
    if is_active is not None:
        old = reason.is_active
        reason.is_active = is_active
        log_value_change(
            db,
            username,
            "update",
            "mes_qc_rejection_reason",
            reason.id,
            "is_active",
            old,
            is_active,
        )
    reason.updated_at = datetime.utcnow()
    return serialize_rejection_reason(reason)
