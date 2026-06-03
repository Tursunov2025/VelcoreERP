"""Material consumption planning (P4-A2)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from models import (
    Material,
    MaterialBomLine,
    MaterialReservation,
    MesJobBomLine,
    MesProductPart,
    MesProductionJob,
)
from services.audit import log_value_change
from services.mes_bom import get_active_part

ACTIVE_RESERVATION_JOB_STATUSES = ("released", "in_progress", "on_hold")


def serialize_material_bom_line(line: MaterialBomLine) -> dict:
    mat = line.material
    return {
        "id": line.id,
        "part_id": line.part_id,
        "material_id": line.material_id,
        "material_code": mat.code if mat else "",
        "material_name": mat.name if mat else "",
        "material_unit": mat.unit if mat else "",
        "quantity_per_part": float(line.quantity_per_part or 0),
        "sort_order": line.sort_order,
        "is_active": bool(line.is_active),
    }


def serialize_reservation(res: MaterialReservation) -> dict:
    mat = res.material
    job = res.job
    available = float(mat.quantity or 0) if mat else 0.0
    required = float(res.required_quantity or 0)
    shortage = max(0.0, required - available)
    return {
        "id": res.id,
        "job_id": res.job_id,
        "job_number": job.job_number if job else "",
        "job_status": job.status if job else "",
        "material_id": res.material_id,
        "material_code": mat.code if mat else "",
        "material_name": mat.name if mat else "",
        "material_unit": mat.unit if mat else "",
        "required_quantity": required,
        "reserved_quantity": float(res.reserved_quantity or 0),
        "available_quantity": available,
        "shortage_quantity": shortage,
        "created_at": res.created_at,
    }


def list_part_material_bom(db: Session, part_id: int, *, include_inactive: bool = False) -> list[dict]:
    get_active_part(db, part_id)
    query = (
        db.query(MaterialBomLine)
        .options(joinedload(MaterialBomLine.material))
        .filter(MaterialBomLine.part_id == part_id)
        .order_by(MaterialBomLine.sort_order, MaterialBomLine.id)
    )
    if not include_inactive:
        query = query.filter(MaterialBomLine.is_active.is_(True))
    return [serialize_material_bom_line(line) for line in query.all()]


def add_part_material_bom_line(
    db: Session,
    username: str,
    *,
    part_id: int,
    material_id: int,
    quantity_per_part: float,
) -> dict:
    get_active_part(db, part_id)
    qty = float(quantity_per_part)
    if qty <= 0:
        raise ValueError("Quantity per part must be positive")

    mat = db.query(Material).filter(Material.id == material_id, Material.is_active.is_(True)).first()
    if not mat:
        raise ValueError("Material not found")

    existing = (
        db.query(MaterialBomLine)
        .filter(
            MaterialBomLine.part_id == part_id,
            MaterialBomLine.material_id == material_id,
            MaterialBomLine.is_active.is_(True),
        )
        .first()
    )
    if existing:
        raise ValueError("Material already attached to this part")

    max_sort = (
        db.query(MaterialBomLine.sort_order)
        .filter(MaterialBomLine.part_id == part_id)
        .order_by(MaterialBomLine.sort_order.desc())
        .first()
    )
    line = MaterialBomLine(
        part_id=part_id,
        material_id=material_id,
        quantity_per_part=qty,
        sort_order=(max_sort[0] + 1) if max_sort else 0,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(line)
    db.flush()
    log_value_change(
        db,
        username,
        "create",
        "material_bom_line",
        line.id,
        "quantity_per_part",
        None,
        qty,
    )
    db.refresh(line, attribute_names=["material"])
    return serialize_material_bom_line(line)


def update_part_material_bom_line(
    db: Session,
    line: MaterialBomLine,
    username: str,
    *,
    quantity_per_part: float | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
) -> dict:
    if quantity_per_part is not None:
        qty = float(quantity_per_part)
        if qty <= 0:
            raise ValueError("Quantity per part must be positive")
        if qty != line.quantity_per_part:
            log_value_change(
                db,
                username,
                "update",
                "material_bom_line",
                line.id,
                "quantity_per_part",
                line.quantity_per_part,
                qty,
            )
            line.quantity_per_part = qty
    if sort_order is not None:
        line.sort_order = sort_order
    if is_active is not None:
        line.is_active = is_active
    line.updated_at = datetime.utcnow()
    db.refresh(line, attribute_names=["material"])
    return serialize_material_bom_line(line)


def get_part_material_bom_line(db: Session, part_id: int, line_id: int) -> MaterialBomLine | None:
    return (
        db.query(MaterialBomLine)
        .options(joinedload(MaterialBomLine.material))
        .filter(MaterialBomLine.part_id == part_id, MaterialBomLine.id == line_id)
        .first()
    )


def calculate_job_material_requirements(db: Session, job: MesProductionJob) -> dict[int, float]:
    """Aggregate required raw material by material_id for a job snapshot."""
    requirements: dict[int, float] = defaultdict(float)
    bom_lines = (
        db.query(MesJobBomLine)
        .filter(MesJobBomLine.job_id == job.id)
        .all()
    )
    if not bom_lines:
        return {}

    part_ids = {line.part_id for line in bom_lines}
    material_lines = (
        db.query(MaterialBomLine)
        .filter(
            MaterialBomLine.part_id.in_(part_ids),
            MaterialBomLine.is_active.is_(True),
        )
        .all()
    )
    by_part: dict[int, list[MaterialBomLine]] = defaultdict(list)
    for ml in material_lines:
        by_part[ml.part_id].append(ml)

    for job_line in bom_lines:
        parts_needed = float(job_line.allocated_quantity or 0)
        for ml in by_part.get(job_line.part_id, []):
            requirements[ml.material_id] += parts_needed * float(ml.quantity_per_part or 0)

    return dict(requirements)


def _available_for_reservation(
    db: Session,
    material_id: int,
    *,
    exclude_job_id: int | None = None,
) -> float:
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        return 0.0
    stock = float(mat.quantity or 0)
    query = (
        db.query(MaterialReservation)
        .join(MesProductionJob, MaterialReservation.job_id == MesProductionJob.id)
        .filter(
            MaterialReservation.material_id == material_id,
            MesProductionJob.status.in_(ACTIVE_RESERVATION_JOB_STATUSES),
        )
    )
    if exclude_job_id:
        query = query.filter(MaterialReservation.job_id != exclude_job_id)
    committed = sum(float(r.reserved_quantity or 0) for r in query.all())
    return max(0.0, stock - committed)


def sync_job_material_reservations(db: Session, job: MesProductionJob) -> list[MaterialReservation]:
    """Create/update material reservations when a job is released (no stock deduction)."""
    job.material_reservations.clear()
    db.flush()

    requirements = calculate_job_material_requirements(db, job)
    now = datetime.utcnow()
    created: list[MaterialReservation] = []

    for material_id, required in requirements.items():
        if required <= 0:
            continue
        available = _available_for_reservation(db, material_id, exclude_job_id=job.id)
        reserved = min(available, required)
        res = MaterialReservation(
            job_id=job.id,
            material_id=material_id,
            required_quantity=round(required, 4),
            reserved_quantity=round(reserved, 4),
            created_at=now,
            updated_at=now,
        )
        db.add(res)
        created.append(res)

    db.flush()
    return created


def list_job_reservations(db: Session, job_id: int) -> list[dict]:
    rows = (
        db.query(MaterialReservation)
        .options(
            joinedload(MaterialReservation.material),
            joinedload(MaterialReservation.job),
        )
        .filter(MaterialReservation.job_id == job_id)
        .order_by(MaterialReservation.material_id)
        .all()
    )
    return [serialize_reservation(r) for r in rows]


def planning_shortages(db: Session) -> list[dict]:
    """Dashboard: aggregate shortages for active jobs."""
    rows = (
        db.query(MaterialReservation)
        .options(
            joinedload(MaterialReservation.material),
            joinedload(MaterialReservation.job),
        )
        .join(MesProductionJob, MaterialReservation.job_id == MesProductionJob.id)
        .filter(MesProductionJob.status.in_(ACTIVE_RESERVATION_JOB_STATUSES))
        .all()
    )

    by_material: dict[int, dict] = {}
    for res in rows:
        mat = res.material
        if not mat:
            continue
        mid = mat.id
        if mid not in by_material:
            by_material[mid] = {
                "material_id": mid,
                "material_code": mat.code or "",
                "material_name": mat.name or "",
                "material_unit": mat.unit or "",
                "required_quantity": 0.0,
                "reserved_quantity": 0.0,
                "available_quantity": float(mat.quantity or 0),
                "shortage_quantity": 0.0,
                "job_count": 0,
                "jobs": [],
            }
        entry = by_material[mid]
        req = float(res.required_quantity or 0)
        entry["required_quantity"] += req
        entry["reserved_quantity"] += float(res.reserved_quantity or 0)
        entry["job_count"] += 1
        if res.job:
            entry["jobs"].append(
                {
                    "job_id": res.job_id,
                    "job_number": res.job.job_number,
                    "required_quantity": req,
                    "reserved_quantity": float(res.reserved_quantity or 0),
                }
            )

    result = []
    for entry in by_material.values():
        entry["required_quantity"] = round(entry["required_quantity"], 4)
        entry["reserved_quantity"] = round(entry["reserved_quantity"], 4)
        available = entry["available_quantity"]
        entry["shortage_quantity"] = round(max(0.0, entry["required_quantity"] - available), 4)
        result.append(entry)

    result.sort(key=lambda x: (-x["shortage_quantity"], x["material_code"]))
    return result


def planning_dashboard(db: Session) -> dict:
    shortages = planning_shortages(db)
    return {
        "shortage_count": sum(1 for s in shortages if s["shortage_quantity"] > 0),
        "materials_planned": len(shortages),
        "total_required": round(sum(s["required_quantity"] for s in shortages), 2),
        "shortages": shortages,
    }


def list_parts_with_material_bom(db: Session) -> list[dict]:
    parts = (
        db.query(MesProductPart)
        .options(joinedload(MesProductPart.material_bom_lines))
        .filter(
            MesProductPart.is_active.is_(True),
            MesProductPart.deleted_at.is_(None),
        )
        .order_by(MesProductPart.part_number)
        .all()
    )
    return [
        {
            "id": p.id,
            "part_number": p.part_number,
            "name": p.name,
            "unit": p.unit,
            "material_bom_count": sum(1 for l in p.material_bom_lines if l.is_active),
        }
        for p in parts
    ]
