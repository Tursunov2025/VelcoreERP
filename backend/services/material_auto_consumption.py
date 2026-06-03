"""Automatic material consumption on MES stage start (P4-A3)."""

from __future__ import annotations

from datetime import datetime, time

from sqlalchemy.orm import Session, joinedload

from models import (
    Material,
    MaterialCategory,
    MaterialConsumption,
    MaterialConsumptionRule,
    MaterialReservation,
    MaterialStockMovement,
    MesProductionJob,
)
from services.audit import log_value_change
from services.materials_warehouse import create_issue, get_material

from services.settings_runtime import get_auto_consume_stages, is_auto_consume_enabled

CONSUMPTION_STAGES = ("Lazer", "Kraska")

STAGE_CATEGORY_CODES = {
    "Lazer": "METAL",
    "Kraska": "PAINT",
}


def serialize_consumption_rule(rule: MaterialConsumptionRule) -> dict:
    mat = rule.material
    return {
        "id": rule.id,
        "material_id": rule.material_id,
        "material_code": mat.code if mat else "",
        "material_name": mat.name if mat else "",
        "material_unit": mat.unit if mat else "",
        "consuming_stage": rule.consuming_stage,
        "is_active": bool(rule.is_active),
    }


def serialize_consumption(record: MaterialConsumption) -> dict:
    mat = record.material
    job = record.job
    unit_cost = float(mat.unit_cost or 0) if mat else 0.0
    qty = float(record.quantity or 0)
    return {
        "id": record.id,
        "job_id": record.job_id,
        "job_number": job.job_number if job else "",
        "material_id": record.material_id,
        "material_code": mat.code if mat else "",
        "material_name": mat.name if mat else "",
        "material_unit": mat.unit if mat else "",
        "quantity": qty,
        "unit_cost": unit_cost,
        "line_cost": round(qty * unit_cost, 2),
        "stage": record.stage,
        "movement_id": record.movement_id,
        "consumed_at": record.consumed_at,
    }


def seed_consumption_rules(db: Session) -> None:
    """Default: METAL materials → Lazer, PAINT materials → Kraska."""
    categories = {
        c.code: c.id for c in db.query(MaterialCategory).filter(MaterialCategory.is_active.is_(True)).all()
    }
    for stage, cat_code in STAGE_CATEGORY_CODES.items():
        cat_id = categories.get(cat_code)
        if not cat_id:
            continue
        materials = (
            db.query(Material)
            .filter(Material.category_id == cat_id, Material.is_active.is_(True))
            .all()
        )
        for mat in materials:
            existing = (
                db.query(MaterialConsumptionRule)
                .filter(
                    MaterialConsumptionRule.material_id == mat.id,
                    MaterialConsumptionRule.consuming_stage == stage,
                )
                .first()
            )
            if not existing:
                db.add(
                    MaterialConsumptionRule(
                        material_id=mat.id,
                        consuming_stage=stage,
                        is_active=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )
            else:
                existing.is_active = True
                existing.updated_at = datetime.utcnow()
    db.commit()


def list_consumption_rules(db: Session, *, include_inactive: bool = False) -> list[dict]:
    query = (
        db.query(MaterialConsumptionRule)
        .options(joinedload(MaterialConsumptionRule.material))
        .order_by(MaterialConsumptionRule.consuming_stage, MaterialConsumptionRule.material_id)
    )
    if not include_inactive:
        query = query.filter(MaterialConsumptionRule.is_active.is_(True))
    return [serialize_consumption_rule(r) for r in query.all()]


def create_consumption_rule(
    db: Session,
    username: str,
    *,
    material_id: int,
    consuming_stage: str,
) -> dict:
    stage = (consuming_stage or "").strip()
    allowed = get_auto_consume_stages(db)
    if stage not in allowed:
        raise ValueError(f"Invalid stage; allowed: {', '.join(allowed)}")
    mat = get_material(db, material_id)
    if not mat or not mat.is_active:
        raise ValueError("Material not found")

    dup = (
        db.query(MaterialConsumptionRule)
        .filter(
            MaterialConsumptionRule.material_id == material_id,
            MaterialConsumptionRule.consuming_stage == stage,
            MaterialConsumptionRule.is_active.is_(True),
        )
        .first()
    )
    if dup:
        raise ValueError("Consumption rule already exists")

    rule = MaterialConsumptionRule(
        material_id=material_id,
        consuming_stage=stage,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(rule)
    db.flush()
    log_value_change(
        db, username, "create", "material_consumption_rule", rule.id, "consuming_stage", None, stage
    )
    db.refresh(rule, attribute_names=["material"])
    return serialize_consumption_rule(rule)


def update_consumption_rule(
    db: Session,
    rule: MaterialConsumptionRule,
    username: str,
    *,
    is_active: bool | None = None,
) -> dict:
    if is_active is not None:
        old = rule.is_active
        rule.is_active = is_active
        log_value_change(
            db, username, "update", "material_consumption_rule", rule.id, "is_active", old, is_active
        )
    rule.updated_at = datetime.utcnow()
    db.refresh(rule, attribute_names=["material"])
    return serialize_consumption_rule(rule)


def _rule_material_ids(db: Session, stage: str) -> set[int]:
    rows = (
        db.query(MaterialConsumptionRule.material_id)
        .filter(
            MaterialConsumptionRule.consuming_stage == stage,
            MaterialConsumptionRule.is_active.is_(True),
        )
        .all()
    )
    return {r[0] for r in rows}


def _already_consumed(db: Session, job_id: int, material_id: int, stage: str) -> bool:
    return (
        db.query(MaterialConsumption)
        .filter(
            MaterialConsumption.job_id == job_id,
            MaterialConsumption.material_id == material_id,
            MaterialConsumption.stage == stage,
        )
        .first()
        is not None
    )


def auto_consume_on_stage_start(
    db: Session,
    job: MesProductionJob,
    stage_name: str,
    username: str,
) -> list[MaterialConsumption]:
    """Issue stock for job materials configured for this stage. Raises on insufficient stock."""
    stage = (stage_name or "").strip()
    allowed = get_auto_consume_stages(db)
    if stage not in allowed:
        return []
    if not is_auto_consume_enabled(db):
        return []

    rule_ids = _rule_material_ids(db, stage)
    if not rule_ids:
        return []

    reservations = (
        db.query(MaterialReservation)
        .options(joinedload(MaterialReservation.material))
        .filter(MaterialReservation.job_id == job.id)
        .all()
    )

    pending: list[tuple[int, float, Material]] = []
    for res in reservations:
        if res.material_id not in rule_ids:
            continue
        if _already_consumed(db, job.id, res.material_id, stage):
            continue
        qty = float(res.required_quantity or 0)
        if qty <= 0:
            continue
        mat = res.material or get_material(db, res.material_id)
        if not mat:
            continue
        pending.append((res.material_id, qty, mat))

    for _mid, qty, mat in pending:
        available = float(mat.quantity or 0)
        if available < qty:
            code = mat.code or mat.name
            raise ValueError(
                f"Insufficient stock for {code}: need {qty}, available {available}"
            )

    created: list[MaterialConsumption] = []
    now = datetime.utcnow()
    for material_id, qty, mat in pending:
        result = create_issue(
            db,
            username,
            material_id=material_id,
            quantity=qty,
            reason=f"Auto consumption — {stage}",
            reference=job.job_number,
            notes=f"Job {job.job_number} · stage {stage}",
        )
        record = MaterialConsumption(
            job_id=job.id,
            material_id=material_id,
            quantity=qty,
            stage=stage,
            movement_id=result.get("movement_id"),
            consumed_at=now,
        )
        db.add(record)
        created.append(record)
        log_value_change(
            db,
            username,
            "auto_consume",
            "material_consumption",
            job.id,
            mat.code or mat.name,
            None,
            qty,
        )

    if created:
        db.flush()
    return created


def list_job_consumptions(db: Session, job_id: int) -> list[dict]:
    rows = (
        db.query(MaterialConsumption)
        .options(
            joinedload(MaterialConsumption.material),
            joinedload(MaterialConsumption.job),
        )
        .filter(MaterialConsumption.job_id == job_id)
        .order_by(MaterialConsumption.consumed_at)
        .all()
    )
    return [serialize_consumption(r) for r in rows]


def job_material_cost(db: Session, job_id: int) -> dict:
    job = db.query(MesProductionJob).filter(MesProductionJob.id == job_id).first()
    if not job:
        raise ValueError("Job not found")

    lines = list_job_consumptions(db, job_id)
    total_cost = round(sum(line["line_cost"] for line in lines), 2)
    by_stage: dict[str, float] = {}
    for line in lines:
        by_stage[line["stage"]] = round(by_stage.get(line["stage"], 0.0) + line["line_cost"], 2)

    return {
        "job_id": job.id,
        "job_number": job.job_number,
        "total_cost": total_cost,
        "by_stage": by_stage,
        "lines": lines,
    }


def consumptions_today_stats(db: Session) -> dict:
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    rows = (
        db.query(MaterialConsumption)
        .filter(MaterialConsumption.consumed_at >= today_start)
        .all()
    )
    total_qty = round(sum(float(r.quantity or 0) for r in rows), 4)
    total_cost = 0.0
    for r in rows:
        mat = db.query(Material).filter(Material.id == r.material_id).first()
        if mat:
            total_cost += float(r.quantity or 0) * float(mat.unit_cost or 0)
    return {
        "consumed_today": len(rows),
        "consumed_quantity_today": total_qty,
        "consumed_cost_today": round(total_cost, 2),
    }


def list_consumptions_today(db: Session, limit: int = 100) -> list[dict]:
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    rows = (
        db.query(MaterialConsumption)
        .options(
            joinedload(MaterialConsumption.material),
            joinedload(MaterialConsumption.job),
        )
        .filter(MaterialConsumption.consumed_at >= today_start)
        .order_by(MaterialConsumption.consumed_at.desc())
        .limit(limit)
        .all()
    )
    return [serialize_consumption(r) for r in rows]
