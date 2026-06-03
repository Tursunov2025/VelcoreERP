"""Finished goods warehouse (Sklad) terminal."""

from __future__ import annotations

from datetime import datetime, time

from sqlalchemy.orm import Session, joinedload

from models import (
    MesFinishedGoodsInventory,
    MesInventoryMovement,
    MesJobPackage,
    MesJobRouteStep,
    MesProductionJob,
    MesProductionStage,
    MesWarehouseLocation,
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

WAREHOUSE_STAGE_NAME = "Sklad"
DISPATCH_STAGE_NAME = "Yuklash"
WAREHOUSE_DEPARTMENT = "Ombor"

DEFAULT_WAREHOUSE_LOCATIONS = ["A-01-01", "A-01-02", "B-01-01"]


def get_warehouse_stages(db: Session) -> list[MesProductionStage]:
    return (
        db.query(MesProductionStage)
        .filter(
            MesProductionStage.is_active.is_(True),
            MesProductionStage.name == WAREHOUSE_STAGE_NAME,
        )
        .order_by(MesProductionStage.sort_order, MesProductionStage.name)
        .all()
    )


def warehouse_stage_ids(db: Session) -> set[int]:
    return {stage.id for stage in get_warehouse_stages(db)}


def get_current_warehouse_step(
    job: MesProductionJob, warehouse_ids: set[int]
) -> MesJobRouteStep | None:
    active = get_active_step(job)
    if active and active.stage_id in warehouse_ids:
        return active
    return None


def find_warehouse_step(
    job: MesProductionJob, warehouse_ids: set[int]
) -> MesJobRouteStep | None:
    current = get_current_warehouse_step(job, warehouse_ids)
    if current:
        return current
    return next((s for s in ordered_steps(job) if s.stage_id in warehouse_ids), None)


def job_in_warehouse_queue(job: MesProductionJob, warehouse_ids: set[int]) -> bool:
    if job.status not in QUEUE_JOB_STATUSES:
        return False
    active = get_active_step(job)
    if not active or active.stage_id not in warehouse_ids:
        return False
    return prior_steps_complete(job, active)


def receivable_packages(job: MesProductionJob) -> list[MesJobPackage]:
    return [
        p
        for p in (job.packages or [])
        if p.status in ("packed", "received", "placed") and p.status != "cancelled"
    ]


def placed_packages(job: MesProductionJob) -> list[MesJobPackage]:
    return [p for p in receivable_packages(job) if p.location_id is not None]


def placement_progress_pct(job: MesProductionJob) -> float:
    packages = receivable_packages(job)
    if not packages:
        return 0.0
    placed = len(placed_packages(job))
    return min(100.0, round((placed / len(packages)) * 100.0, 2))


def serialize_location(loc: MesWarehouseLocation) -> dict:
    return {
        "id": loc.id,
        "code": loc.code,
        "description": loc.description or "",
        "sort_order": loc.sort_order,
        "is_active": bool(loc.is_active),
    }


def serialize_package_terminal(
    pkg: MesJobPackage, *, location_code: str | None = None
) -> dict:
    loc_code = location_code
    if loc_code is None and pkg.location:
        loc_code = pkg.location.code
    return {
        "id": pkg.id,
        "job_id": pkg.job_id,
        "package_number": pkg.package_number,
        "package_type": pkg.package_type or "",
        "net_weight_kg": float(pkg.net_weight_kg or 0),
        "gross_weight_kg": float(pkg.gross_weight_kg or 0),
        "status": pkg.status,
        "location_id": pkg.location_id,
        "location_code": loc_code,
        "received_at": pkg.received_at,
        "placed_at": pkg.placed_at,
    }


def serialize_terminal_job(
    job: MesProductionJob,
    warehouse_ids: set[int],
    *,
    include_packages: bool = True,
) -> dict:
    warehouse_step = find_warehouse_step(job, warehouse_ids)
    current_step = get_current_warehouse_step(job, warehouse_ids) or warehouse_step
    packages = receivable_packages(job)
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
        "warehouse_step": serialize_route_step(current_step),
        "step_state": terminal_step_state(current_step),
        "overall_progress_pct": placement_progress_pct(job),
        "package_total": len(packages),
        "packages_placed": len(placed_packages(job)),
    }
    if include_packages:
        sorted_pkgs = sorted(packages, key=lambda p: p.package_number)
        payload["packages"] = [serialize_package_terminal(p) for p in sorted_pkgs]
    return payload


def list_warehouse_queue(db: Session, warehouse_ids: set[int]) -> list[dict]:
    jobs = (
        db.query(MesProductionJob)
        .options(
            joinedload(MesProductionJob.template),
            joinedload(MesProductionJob.packages).joinedload(MesJobPackage.location),
            joinedload(MesProductionJob.route_steps),
        )
        .filter(MesProductionJob.status.in_(QUEUE_JOB_STATUSES))
        .all()
    )
    queue = []
    for job in jobs:
        if not job_in_warehouse_queue(job, warehouse_ids):
            continue
        if not receivable_packages(job):
            continue
        queue.append(serialize_terminal_job(job, warehouse_ids, include_packages=False))
    return sort_queue(queue)


def warehouse_dashboard(db: Session, warehouse_ids: set[int]) -> dict:
    queue = list_warehouse_queue(db, warehouse_ids)
    waiting = sum(1 for job in queue if job.get("step_state") in ("pending_accept", "accepted"))
    active = sum(1 for job in queue if job.get("step_state") == "in_progress")

    inventory_items = (
        db.query(MesFinishedGoodsInventory)
        .filter(MesFinishedGoodsInventory.status == "in_stock")
        .count()
    )

    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    received_today = (
        db.query(MesJobRouteStep)
        .filter(
            MesJobRouteStep.stage_id.in_(warehouse_ids),
            MesJobRouteStep.completed_at.isnot(None),
            MesJobRouteStep.completed_at >= today_start,
        )
        .count()
    )

    return {
        "waiting_receipts": waiting,
        "active_placements": active,
        "inventory_items": inventory_items,
        "received_today": received_today,
    }


def list_inventory_summary(db: Session) -> list[dict]:
    rows = (
        db.query(MesFinishedGoodsInventory)
        .options(joinedload(MesFinishedGoodsInventory.location))
        .filter(MesFinishedGoodsInventory.status == "in_stock")
        .all()
    )
    grouped: dict[tuple[int, str, str], dict] = {}
    for row in rows:
        key = (row.template_id, row.product_code, row.product_name)
        if key not in grouped:
            grouped[key] = {
                "template_id": row.template_id,
                "product_code": row.product_code,
                "product_name": row.product_name,
                "quantity": 0.0,
                "unit": row.unit or "dona",
                "locations": set(),
                "package_count": 0,
            }
        grouped[key]["quantity"] += float(row.quantity or 0)
        grouped[key]["package_count"] += 1
        if row.location:
            grouped[key]["locations"].add(row.location.code)

    result = []
    for item in grouped.values():
        result.append(
            {
                "template_id": item["template_id"],
                "product_code": item["product_code"],
                "product_name": item["product_name"],
                "quantity": round(item["quantity"], 3),
                "unit": item["unit"],
                "locations": sorted(item["locations"]),
                "package_count": item["package_count"],
            }
        )
    result.sort(key=lambda x: (x["product_code"], x["product_name"]))
    return result


def _require_warehouse_step(job: MesProductionJob, warehouse_ids: set[int]) -> MesJobRouteStep:
    if job.status not in QUEUE_JOB_STATUSES:
        raise ValueError("Job is not active for warehouse work")
    step = get_current_warehouse_step(job, warehouse_ids)
    if not step:
        raise ValueError("Job is not waiting at warehouse stage")
    if step.completed_at:
        raise ValueError("Warehouse receipt already completed")
    return step


def _log_movement(
    db: Session,
    *,
    movement_type: str,
    username: str,
    job_id: int | None = None,
    package_id: int | None = None,
    inventory_id: int | None = None,
    from_location_id: int | None = None,
    to_location_id: int | None = None,
    quantity: float = 1.0,
    notes: str = "",
) -> MesInventoryMovement:
    movement = MesInventoryMovement(
        job_id=job_id,
        package_id=package_id,
        inventory_id=inventory_id,
        movement_type=movement_type,
        from_location_id=from_location_id,
        to_location_id=to_location_id,
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
    return movement


def accept_warehouse_receipt(
    db: Session, job: MesProductionJob, warehouse_ids: set[int], username: str
) -> None:
    step = _require_warehouse_step(job, warehouse_ids)
    if step.accepted_at:
        raise ValueError("Receipt already accepted")
    packages = receivable_packages(job)
    if not packages:
        raise ValueError("No packed packages to receive")

    now = datetime.utcnow()
    log_value_change(
        db, username, "accept", "mes_job_route_step", step.id, "accepted_at", None, now.isoformat()
    )
    step.accepted_at = now

    for pkg in packages:
        if pkg.received_at:
            continue
        old_status = pkg.status
        pkg.received_at = now
        if pkg.status == "packed":
            pkg.status = "received"
            log_value_change(
                db,
                username,
                "receive",
                "mes_job_package",
                pkg.id,
                "status",
                old_status,
                pkg.status,
            )
        _log_movement(
            db,
            movement_type="receipt",
            username=username,
            job_id=job.id,
            package_id=pkg.id,
            quantity=1.0,
            notes=f"Receipt accepted for {pkg.package_number}",
        )

    job.updated_at = now


def start_warehouse_placement(
    db: Session, job: MesProductionJob, warehouse_ids: set[int], username: str
) -> None:
    step = _require_warehouse_step(job, warehouse_ids)
    if not step.accepted_at:
        raise ValueError("Accept receipt before starting placement")
    if step.started_at:
        raise ValueError("Placement already started")
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


def assign_package_to_location(
    db: Session,
    job: MesProductionJob,
    warehouse_ids: set[int],
    username: str,
    *,
    package_id: int,
    location_id: int,
) -> MesFinishedGoodsInventory:
    step = _require_warehouse_step(job, warehouse_ids)
    if not step.started_at:
        raise ValueError("Start placement before assigning locations")

    location = (
        db.query(MesWarehouseLocation)
        .filter(
            MesWarehouseLocation.id == location_id,
            MesWarehouseLocation.is_active.is_(True),
        )
        .first()
    )
    if not location:
        raise ValueError("Warehouse location not found")

    pkg = next((p for p in receivable_packages(job) if p.id == package_id), None)
    if not pkg:
        raise ValueError("Package not found on job")

    if pkg.location_id:
        raise ValueError(f"Package {pkg.package_number} already placed")

    template = job.template
    if not template:
        raise ValueError("Job template missing")

    now = datetime.utcnow()
    old_loc = pkg.location_id
    pkg.location_id = location_id
    pkg.placed_at = now
    old_status = pkg.status
    pkg.status = "placed"
    log_value_change(
        db,
        username,
        "place",
        "mes_job_package",
        pkg.id,
        "location_id",
        old_loc,
        location_id,
    )
    if old_status != pkg.status:
        log_value_change(
            db,
            username,
            "place",
            "mes_job_package",
            pkg.id,
            "status",
            old_status,
            pkg.status,
        )

    existing_inv = (
        db.query(MesFinishedGoodsInventory)
        .filter(MesFinishedGoodsInventory.package_id == pkg.id)
        .first()
    )
    if existing_inv:
        raise ValueError("Inventory record already exists for package")

    inventory = MesFinishedGoodsInventory(
        job_id=job.id,
        package_id=pkg.id,
        template_id=template.id,
        product_code=template.code,
        product_name=template.name,
        location_id=location_id,
        quantity=1.0,
        unit=template.unit or "dona",
        status="in_stock",
        received_at=pkg.received_at or now,
        placed_at=now,
        created_at=now,
        updated_at=now,
        created_by=username,
    )
    db.add(inventory)
    db.flush()

    _log_movement(
        db,
        movement_type="placement",
        username=username,
        job_id=job.id,
        package_id=pkg.id,
        inventory_id=inventory.id,
        to_location_id=location_id,
        quantity=1.0,
        notes=f"Placed {pkg.package_number} at {location.code}",
    )

    job.updated_at = now
    step.completed_parts_count = len(placed_packages(job))
    return inventory


def _complete_warehouse_step(
    db: Session,
    job: MesProductionJob,
    step: MesJobRouteStep,
    username: str,
) -> None:
    if step.completed_at:
        return

    packages = receivable_packages(job)
    if not packages:
        raise ValueError("No packages to receive")
    unplaced = [p for p in packages if not p.location_id]
    if unplaced:
        raise ValueError("Place all packages before completing receipt")

    now = datetime.utcnow()
    old_completed_at = step.completed_at.isoformat() if step.completed_at else None
    step.completed_at = now
    step.completed_parts_count = len(packages)
    log_value_change(
        db,
        username,
        "complete",
        "mes_job_route_step",
        step.id,
        "completed_at",
        old_completed_at,
        now.isoformat(),
    )

    dispatch_step = next(
        (s for s in ordered_steps(job) if s.stage_name == DISPATCH_STAGE_NAME and s.is_required),
        None,
    )
    if dispatch_step:
        log_value_change(
            db,
            username,
            "dispatch_transition",
            "mes_production_job",
            job.id,
            "active_stage",
            step.stage_name,
            dispatch_step.stage_name,
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


def complete_warehouse_receipt(
    db: Session, job: MesProductionJob, warehouse_ids: set[int], username: str
) -> None:
    step = _require_warehouse_step(job, warehouse_ids)
    if not step.started_at:
        raise ValueError("Start placement before completing")
    _complete_warehouse_step(db, job, step, username)


def load_warehouse_job(db: Session, job_id: int) -> MesProductionJob | None:
    return (
        db.query(MesProductionJob)
        .options(
            joinedload(MesProductionJob.template),
            joinedload(MesProductionJob.packages).joinedload(MesJobPackage.location),
            joinedload(MesProductionJob.route_steps),
        )
        .filter(MesProductionJob.id == job_id)
        .first()
    )


# --- Location management ---


def seed_warehouse_locations(db: Session) -> None:
    for order, code in enumerate(DEFAULT_WAREHOUSE_LOCATIONS):
        existing = (
            db.query(MesWarehouseLocation).filter(MesWarehouseLocation.code == code).first()
        )
        if not existing:
            db.add(
                MesWarehouseLocation(
                    code=code,
                    description="",
                    sort_order=order,
                    is_active=True,
                    created_by="system",
                )
            )
    db.commit()


def list_locations(db: Session, *, include_inactive: bool = False) -> list[dict]:
    query = db.query(MesWarehouseLocation).order_by(
        MesWarehouseLocation.sort_order, MesWarehouseLocation.code
    )
    if not include_inactive:
        query = query.filter(MesWarehouseLocation.is_active.is_(True))
    return [serialize_location(loc) for loc in query.all()]


def create_location(db: Session, username: str, code: str, description: str = "") -> dict:
    clean = (code or "").strip().upper()
    if not clean:
        raise ValueError("Location code is required")
    existing = (
        db.query(MesWarehouseLocation)
        .filter(MesWarehouseLocation.code == clean)
        .first()
    )
    if existing and existing.is_active:
        raise ValueError("Location code already exists")
    if existing:
        existing.is_active = True
        existing.description = description.strip()
        existing.updated_at = datetime.utcnow()
        log_value_change(
            db, username, "reactivate", "mes_warehouse_location", existing.id, "is_active", False, True
        )
        return serialize_location(existing)

    loc = MesWarehouseLocation(
        code=clean,
        description=description.strip(),
        sort_order=0,
        is_active=True,
        created_by=username,
    )
    db.add(loc)
    db.flush()
    log_value_change(
        db, username, "create", "mes_warehouse_location", loc.id, "code", None, clean
    )
    return serialize_location(loc)


def update_location(
    db: Session,
    loc: MesWarehouseLocation,
    username: str,
    *,
    code: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
    sort_order: int | None = None,
) -> dict:
    if code is not None:
        clean = code.strip().upper()
        if not clean:
            raise ValueError("Location code is required")
        dup = (
            db.query(MesWarehouseLocation)
            .filter(MesWarehouseLocation.code == clean, MesWarehouseLocation.id != loc.id)
            .first()
        )
        if dup:
            raise ValueError("Location code already exists")
        if clean != loc.code:
            log_value_change(
                db, username, "update", "mes_warehouse_location", loc.id, "code", loc.code, clean
            )
            loc.code = clean
    if description is not None:
        loc.description = description.strip()
    if sort_order is not None:
        loc.sort_order = sort_order
    if is_active is not None:
        old = loc.is_active
        loc.is_active = is_active
        log_value_change(
            db,
            username,
            "update",
            "mes_warehouse_location",
            loc.id,
            "is_active",
            old,
            is_active,
        )
    loc.updated_at = datetime.utcnow()
    return serialize_location(loc)
