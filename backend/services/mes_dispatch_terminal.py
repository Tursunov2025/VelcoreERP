"""Yuklash (dispatch) terminal."""

from __future__ import annotations

from datetime import datetime, time

from sqlalchemy.orm import Session, joinedload

from models import (
    MesDispatch,
    MesDispatchPackage,
    MesFinishedGoodsInventory,
    MesInventoryMovement,
    MesJobPackage,
    MesJobRouteStep,
    MesProductionJob,
    MesProductionStage,
)
from services.audit import log_value_change
from services.mes_terminal_common import (
    QUEUE_JOB_STATUSES,
    get_active_step,
    ordered_steps,
    prior_steps_complete,
    serialize_route_step,
    sort_queue,
    terminal_step_state,
)

DISPATCH_STAGE_NAME = "Yuklash"


def get_dispatch_stages(db: Session) -> list[MesProductionStage]:
    return (
        db.query(MesProductionStage)
        .filter(
            MesProductionStage.is_active.is_(True),
            MesProductionStage.name == DISPATCH_STAGE_NAME,
        )
        .order_by(MesProductionStage.sort_order, MesProductionStage.name)
        .all()
    )


def dispatch_stage_ids(db: Session) -> set[int]:
    return {stage.id for stage in get_dispatch_stages(db)}


def get_current_dispatch_step(
    job: MesProductionJob, dispatch_ids: set[int]
) -> MesJobRouteStep | None:
    active = get_active_step(job)
    if active and active.stage_id in dispatch_ids:
        return active
    return None


def find_dispatch_step(job: MesProductionJob, dispatch_ids: set[int]) -> MesJobRouteStep | None:
    current = get_current_dispatch_step(job, dispatch_ids)
    if current:
        return current
    return next((s for s in ordered_steps(job) if s.stage_id in dispatch_ids), None)


def dispatchable_packages(db: Session, job: MesProductionJob) -> list[MesJobPackage]:
    inventory_pkg_ids = {
        row.package_id
        for row in db.query(MesFinishedGoodsInventory)
        .filter(
            MesFinishedGoodsInventory.job_id == job.id,
            MesFinishedGoodsInventory.status == "in_stock",
        )
        .all()
    }
    return [
        p
        for p in (job.packages or [])
        if p.id in inventory_pkg_ids and p.status == "placed" and p.location_id
    ]


def job_in_dispatch_queue(
    db: Session, job: MesProductionJob, dispatch_ids: set[int]
) -> bool:
    if job.status not in QUEUE_JOB_STATUSES:
        return False
    active = get_active_step(job)
    if not active or active.stage_id not in dispatch_ids:
        return False
    if not prior_steps_complete(job, active):
        return False
    return len(dispatchable_packages(db, job)) > 0


def _dispatch_number(job: MesProductionJob) -> str:
    return f"DISP-{job.job_number}"


def get_job_dispatch(db: Session, job_id: int) -> MesDispatch | None:
    return (
        db.query(MesDispatch)
        .options(
            joinedload(MesDispatch.packages)
            .joinedload(MesDispatchPackage.package)
            .joinedload(MesJobPackage.location),
            joinedload(MesDispatch.packages)
            .joinedload(MesDispatchPackage.package)
            .joinedload(MesJobPackage.label),
            joinedload(MesDispatch.packages)
            .joinedload(MesDispatchPackage.package)
            .joinedload(MesJobPackage.storage_location),
        )
        .filter(MesDispatch.job_id == job_id)
        .order_by(MesDispatch.id.desc())
        .first()
    )


def loading_progress_pct(dispatch: MesDispatch | None) -> float:
    if not dispatch or not dispatch.packages:
        return 0.0
    total = len(dispatch.packages)
    loaded = sum(1 for p in dispatch.packages if p.status in ("loaded", "shipped", "delivered"))
    return min(100.0, round((loaded / total) * 100.0, 2))


def serialize_dispatch_package(dp: MesDispatchPackage) -> dict:
    from services.package_traceability import label_fields_for_package

    pkg = dp.package
    extra = label_fields_for_package(pkg) if pkg else {}
    return {
        "id": dp.id,
        "dispatch_id": dp.dispatch_id,
        "package_id": dp.package_id,
        "package_number": pkg.package_number if pkg else "",
        "package_type": pkg.package_type if pkg else "",
        "net_weight_kg": float(pkg.net_weight_kg or 0) if pkg else 0,
        "gross_weight_kg": float(pkg.gross_weight_kg or 0) if pkg else 0,
        "location_code": pkg.location.code if pkg and pkg.location else None,
        "status": dp.status,
        "loaded_at": dp.loaded_at,
        "loaded_by": dp.loaded_by,
        "shipped_at": dp.shipped_at,
        "delivered_at": dp.delivered_at,
        **extra,
    }


def serialize_dispatch(dispatch: MesDispatch | None) -> dict | None:
    if not dispatch:
        return None
    return {
        "id": dispatch.id,
        "dispatch_number": dispatch.dispatch_number,
        "job_id": dispatch.job_id,
        "customer_name": dispatch.customer_name or "",
        "package_count": int(dispatch.package_count or 0),
        "vehicle_number": dispatch.vehicle_number or "",
        "driver_name": dispatch.driver_name or "",
        "driver_phone": dispatch.driver_phone or "",
        "transport_company": dispatch.transport_company or "",
        "status": dispatch.status,
        "ship_date": dispatch.ship_date,
        "delivered_at": dispatch.delivered_at,
        "accepted_at": dispatch.accepted_at,
        "started_at": dispatch.started_at,
        "created_at": dispatch.created_at,
        "loading_progress_pct": loading_progress_pct(dispatch),
        "packages": [serialize_dispatch_package(p) for p in sorted(dispatch.packages or [], key=lambda x: x.id)],
    }


def serialize_terminal_job(
    db: Session,
    job: MesProductionJob,
    dispatch_ids: set[int],
) -> dict:
    dispatch_step = find_dispatch_step(job, dispatch_ids)
    current_step = get_current_dispatch_step(job, dispatch_ids) or dispatch_step
    dispatch = get_job_dispatch(db, job.id)
    packages = dispatchable_packages(db, job)
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
        "dispatch_step": serialize_route_step(current_step),
        "step_state": terminal_step_state(current_step),
        "dispatch": serialize_dispatch(dispatch),
        "available_package_count": len(packages),
        "overall_progress_pct": loading_progress_pct(dispatch),
    }
    return payload


def list_dispatch_queue(db: Session, dispatch_ids: set[int]) -> list[dict]:
    jobs = (
        db.query(MesProductionJob)
        .options(
            joinedload(MesProductionJob.template),
            joinedload(MesProductionJob.packages).joinedload(MesJobPackage.location),
            joinedload(MesProductionJob.packages).joinedload(MesJobPackage.label),
            joinedload(MesProductionJob.packages).joinedload(MesJobPackage.storage_location),
            joinedload(MesProductionJob.route_steps),
        )
        .filter(MesProductionJob.status.in_(QUEUE_JOB_STATUSES))
        .all()
    )
    queue = []
    for job in jobs:
        if not job_in_dispatch_queue(db, job, dispatch_ids):
            continue
        item = serialize_terminal_job(db, job, dispatch_ids)
        queue.append(item)
    return sort_queue(queue)


def dispatch_dashboard(db: Session, dispatch_ids: set[int]) -> dict:
    queue = list_dispatch_queue(db, dispatch_ids)
    waiting = sum(
        1
        for job in queue
        if job.get("step_state") in ("pending_accept", "accepted")
        or (job.get("dispatch") or {}).get("status") == "pending"
    )
    loading = sum(
        1
        for job in queue
        if (job.get("dispatch") or {}).get("status") == "loading"
        or job.get("step_state") == "in_progress"
    )

    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    shipped_today = (
        db.query(MesDispatch)
        .filter(
            MesDispatch.status.in_(("shipped", "delivered")),
            MesDispatch.ship_date.isnot(None),
            MesDispatch.ship_date >= today_start,
        )
        .count()
    )
    delivered_today = (
        db.query(MesDispatch)
        .filter(
            MesDispatch.status == "delivered",
            MesDispatch.delivered_at.isnot(None),
            MesDispatch.delivered_at >= today_start,
        )
        .count()
    )

    return {
        "waiting_dispatch": waiting,
        "loading": loading,
        "shipped_today": shipped_today,
        "delivered_today": delivered_today,
    }


def _require_dispatch_step(job: MesProductionJob, dispatch_ids: set[int]) -> MesJobRouteStep:
    if job.status not in QUEUE_JOB_STATUSES:
        raise ValueError("Job is not active for dispatch")
    step = get_current_dispatch_step(job, dispatch_ids)
    if not step:
        raise ValueError("Job is not at dispatch stage")
    if step.completed_at:
        raise ValueError("Dispatch stage already completed")
    return step


def _log_movement(
    db: Session,
    *,
    movement_type: str,
    username: str,
    job_id: int | None = None,
    package_id: int | None = None,
    inventory_id: int | None = None,
    quantity: float = 1.0,
    notes: str = "",
) -> None:
    movement = MesInventoryMovement(
        job_id=job_id,
        package_id=package_id,
        inventory_id=inventory_id,
        movement_type=movement_type,
        quantity=quantity,
        performed_by=username,
        notes=notes,
        created_at=datetime.utcnow(),
    )
    db.add(movement)
    db.flush()
    log_value_change(
        db,
        username,
        movement_type,
        "mes_inventory_movement",
        movement.id,
        "movement_type",
        None,
        movement_type,
    )


def _create_dispatch_packages(
    db: Session, dispatch: MesDispatch, job: MesProductionJob, username: str
) -> None:
    packages = dispatchable_packages(db, job)
    if not packages:
        raise ValueError("No warehouse packages available for dispatch")

    for pkg in packages:
        existing = (
            db.query(MesDispatchPackage)
            .filter(MesDispatchPackage.package_id == pkg.id)
            .first()
        )
        if existing:
            continue
        inv = (
            db.query(MesFinishedGoodsInventory)
            .filter(
                MesFinishedGoodsInventory.package_id == pkg.id,
                MesFinishedGoodsInventory.status == "in_stock",
            )
            .first()
        )
        dp = MesDispatchPackage(
            dispatch_id=dispatch.id,
            package_id=pkg.id,
            inventory_id=inv.id if inv else None,
            status="pending",
            created_at=datetime.utcnow(),
        )
        db.add(dp)

    dispatch.package_count = len(packages)
    log_value_change(
        db,
        username,
        "create",
        "mes_dispatch",
        dispatch.id,
        "package_count",
        0,
        dispatch.package_count,
    )


def accept_dispatch(
    db: Session, job: MesProductionJob, dispatch_ids: set[int], username: str
) -> MesDispatch:
    step = _require_dispatch_step(job, dispatch_ids)
    if step.accepted_at:
        dispatch = get_job_dispatch(db, job.id)
        if dispatch:
            return dispatch
        raise ValueError("Dispatch already accepted")

    packages = dispatchable_packages(db, job)
    if not packages:
        raise ValueError("No packages in warehouse for dispatch")

    now = datetime.utcnow()
    dispatch = get_job_dispatch(db, job.id)
    if not dispatch:
        dispatch = MesDispatch(
            dispatch_number=_dispatch_number(job),
            job_id=job.id,
            customer_name=job.customer_name or "",
            package_count=len(packages),
            status="pending",
            accepted_at=now,
            created_at=now,
            updated_at=now,
            created_by=username,
        )
        db.add(dispatch)
        db.flush()
        log_value_change(
            db,
            username,
            "create",
            "mes_dispatch",
            dispatch.id,
            "dispatch_number",
            None,
            dispatch.dispatch_number,
        )
        _create_dispatch_packages(db, dispatch, job, username)
    else:
        dispatch.accepted_at = now
        dispatch.status = "pending"
        _create_dispatch_packages(db, dispatch, job, username)

    log_value_change(
        db, username, "accept", "mes_job_route_step", step.id, "accepted_at", None, now.isoformat()
    )
    step.accepted_at = now
    job.updated_at = now
    dispatch.updated_at = now
    return dispatch


def start_loading(
    db: Session, job: MesProductionJob, dispatch_ids: set[int], username: str
) -> MesDispatch:
    step = _require_dispatch_step(job, dispatch_ids)
    dispatch = get_job_dispatch(db, job.id)
    if not dispatch or not dispatch.accepted_at:
        raise ValueError("Accept dispatch before starting loading")
    if dispatch.status not in ("pending", "loading"):
        raise ValueError("Dispatch is not in a loadable state")
    if step.started_at and dispatch.status == "loading":
        return dispatch

    now = datetime.utcnow()
    if not step.started_at:
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

    old_status = dispatch.status
    dispatch.status = "loading"
    dispatch.started_at = now
    dispatch.updated_at = now
    log_value_change(
        db, username, "start", "mes_dispatch", dispatch.id, "status", old_status, dispatch.status
    )
    job.updated_at = now
    return dispatch


def update_transport_info(
    db: Session,
    dispatch: MesDispatch,
    username: str,
    *,
    vehicle_number: str | None = None,
    driver_name: str | None = None,
    driver_phone: str | None = None,
    transport_company: str | None = None,
) -> None:
    fields = {
        "vehicle_number": vehicle_number,
        "driver_name": driver_name,
        "driver_phone": driver_phone,
        "transport_company": transport_company,
    }
    now = datetime.utcnow()
    for field, new_val in fields.items():
        if new_val is None:
            continue
        new = (new_val or "").strip()
        old = getattr(dispatch, field) or ""
        if old == new:
            continue
        log_value_change(db, username, "transport", "mes_dispatch", dispatch.id, field, old, new)
        setattr(dispatch, field, new)
    dispatch.updated_at = now


def load_dispatch_package(
    db: Session,
    job: MesProductionJob,
    dispatch_ids: set[int],
    username: str,
    *,
    package_id: int,
) -> MesDispatchPackage:
    step = _require_dispatch_step(job, dispatch_ids)
    dispatch = get_job_dispatch(db, job.id)
    if not dispatch or dispatch.status != "loading":
        raise ValueError("Start loading before assigning packages")
    if not step.started_at:
        raise ValueError("Start loading before assigning packages")

    dp = next((p for p in (dispatch.packages or []) if p.package_id == package_id), None)
    if not dp:
        raise ValueError("Package not on this dispatch")
    if dp.status != "pending":
        raise ValueError("Package already loaded")

    now = datetime.utcnow()
    old = dp.status
    dp.status = "loaded"
    dp.loaded_at = now
    log_value_change(
        db, username, "load", "mes_dispatch_package", dp.id, "status", old, dp.status
    )
    _log_movement(
        db,
        movement_type="load",
        username=username,
        job_id=job.id,
        package_id=package_id,
        inventory_id=dp.inventory_id,
        notes=f"Loaded {dp.package.package_number if dp.package else package_id}",
    )
    dispatch.updated_at = now
    job.updated_at = now
    return dp


def mark_shipped(
    db: Session, job: MesProductionJob, dispatch_ids: set[int], username: str
) -> MesDispatch:
    step = _require_dispatch_step(job, dispatch_ids)
    dispatch = get_job_dispatch(db, job.id)
    if not dispatch or dispatch.status != "loading":
        raise ValueError("Dispatch must be in loading state")

    pending = [p for p in (dispatch.packages or []) if p.status == "pending"]
    if pending:
        raise ValueError("Load all packages before shipping")

    if not (dispatch.vehicle_number or "").strip():
        raise ValueError("Vehicle number is required before shipping")

    now = datetime.utcnow()
    for dp in dispatch.packages or []:
        if dp.status == "loaded":
            old = dp.status
            dp.status = "shipped"
            dp.shipped_at = now
            log_value_change(
                db, username, "ship", "mes_dispatch_package", dp.id, "status", old, dp.status
            )
            if dp.inventory_id:
                inv = db.query(MesFinishedGoodsInventory).filter(
                    MesFinishedGoodsInventory.id == dp.inventory_id
                ).first()
                if inv and inv.status == "in_stock":
                    inv.status = "dispatched"
                    inv.updated_at = now

    old_status = dispatch.status
    dispatch.status = "shipped"
    dispatch.ship_date = now
    dispatch.updated_at = now
    log_value_change(
        db, username, "ship", "mes_dispatch", dispatch.id, "status", old_status, dispatch.status
    )
    _log_movement(
        db,
        movement_type="dispatch_ship",
        username=username,
        job_id=job.id,
        notes=f"Dispatch {dispatch.dispatch_number} shipped",
    )
    job.updated_at = now
    return dispatch


def mark_delivered(
    db: Session, job: MesProductionJob, dispatch_ids: set[int], username: str
) -> MesDispatch:
    step = _require_dispatch_step(job, dispatch_ids)
    dispatch = get_job_dispatch(db, job.id)
    if not dispatch or dispatch.status != "shipped":
        raise ValueError("Dispatch must be shipped before delivery")

    now = datetime.utcnow()
    for dp in dispatch.packages or []:
        if dp.status == "shipped":
            old = dp.status
            dp.status = "delivered"
            dp.delivered_at = now
            log_value_change(
                db, username, "deliver", "mes_dispatch_package", dp.id, "status", old, dp.status
            )
            if dp.inventory_id:
                inv = db.query(MesFinishedGoodsInventory).filter(
                    MesFinishedGoodsInventory.id == dp.inventory_id
                ).first()
                if inv:
                    inv.status = "delivered"
                    inv.updated_at = now

    old_status = dispatch.status
    dispatch.status = "delivered"
    dispatch.delivered_at = now
    dispatch.updated_at = now
    log_value_change(
        db, username, "deliver", "mes_dispatch", dispatch.id, "status", old_status, dispatch.status
    )

    if not step.completed_at:
        step.completed_at = now
        step.completed_parts_count = len(dispatch.packages or [])
        log_value_change(
            db,
            username,
            "complete",
            "mes_job_route_step",
            step.id,
            "completed_at",
            None,
            now.isoformat(),
        )

    old_job_status = job.status
    job.status = "completed"
    job.completed_at = now
    log_value_change(
        db, username, "status", "mes_production_job", job.id, "status", old_job_status, job.status
    )

    _log_movement(
        db,
        movement_type="dispatch_deliver",
        username=username,
        job_id=job.id,
        notes=f"Dispatch {dispatch.dispatch_number} delivered — job completed",
    )
    job.updated_at = now
    return dispatch


def load_dispatch_job(db: Session, job_id: int) -> MesProductionJob | None:
    return (
        db.query(MesProductionJob)
        .options(
            joinedload(MesProductionJob.template),
            joinedload(MesProductionJob.packages).joinedload(MesJobPackage.location),
            joinedload(MesProductionJob.packages).joinedload(MesJobPackage.label),
            joinedload(MesProductionJob.packages).joinedload(MesJobPackage.storage_location),
            joinedload(MesProductionJob.route_steps),
        )
        .filter(MesProductionJob.id == job_id)
        .first()
    )
