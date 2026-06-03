"""Raw materials warehouse (P4-A1)."""

from __future__ import annotations

from datetime import datetime, time

from sqlalchemy.orm import Session, joinedload

from models import (
    Material,
    MaterialAdjustment,
    MaterialCategory,
    MaterialIssue,
    MaterialReceipt,
    MaterialStockMovement,
)
from services.audit import log_value_change

DEFAULT_CATEGORIES = [
    ("METAL", "Metall"),
    ("PAINT", "Bo'yoq"),
    ("CONS", "Sarf materiallar"),
]


def seed_material_categories(db: Session) -> None:
    from services.settings_runtime import get_material_categories_seed

    categories = get_material_categories_seed(db)
    for order, (code, name) in enumerate(categories):
        existing = db.query(MaterialCategory).filter(MaterialCategory.code == code).first()
        if not existing:
            db.add(
                MaterialCategory(
                    name=name,
                    code=code,
                    sort_order=order,
                    is_active=True,
                )
            )
        else:
            existing.name = name
            existing.sort_order = order
            existing.is_active = True
    db.commit()


def serialize_category(cat: MaterialCategory) -> dict:
    return {
        "id": cat.id,
        "name": cat.name,
        "code": cat.code or "",
        "description": cat.description or "",
        "sort_order": cat.sort_order,
        "is_active": bool(cat.is_active),
    }


def serialize_material(mat: Material) -> dict:
    qty = float(mat.quantity or 0)
    min_stock = float(mat.min_quantity or 0)
    unit_cost = float(mat.unit_cost or 0)
    return {
        "id": mat.id,
        "code": mat.code or "",
        "name": mat.name,
        "unit": mat.unit or "dona",
        "category_id": mat.category_id,
        "category_name": mat.category.name if mat.category else "",
        "minimum_stock": min_stock,
        "current_stock": qty,
        "unit_cost": unit_cost,
        "inventory_value": round(qty * unit_cost, 2),
        "low_stock": qty <= min_stock,
        "is_active": bool(mat.is_active),
        "created_at": mat.created_at,
        "updated_at": mat.updated_at,
    }


def serialize_movement(m: MaterialStockMovement, material: Material | None = None) -> dict:
    mat = material or m.material
    return {
        "id": m.id,
        "material_id": m.material_id,
        "material_code": mat.code if mat else "",
        "material_name": mat.name if mat else "",
        "movement_type": m.movement_type,
        "quantity": float(m.quantity or 0),
        "balance_after": float(m.balance_after or 0),
        "unit_cost": float(m.unit_cost or 0),
        "reference_type": m.reference_type,
        "reference_id": m.reference_id,
        "notes": m.notes or "",
        "created_by": m.created_by,
        "created_at": m.created_at,
    }


def dashboard_stats(db: Session) -> dict:
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    materials = db.query(Material).filter(Material.is_active.is_(True)).all()
    low_stock = sum(1 for m in materials if float(m.quantity or 0) <= float(m.min_quantity or 0))
    inventory_value = round(
        sum(float(m.quantity or 0) * float(m.unit_cost or 0) for m in materials), 2
    )
    receipts_today = (
        db.query(MaterialReceipt).filter(MaterialReceipt.created_at >= today_start).count()
    )
    issues_today = (
        db.query(MaterialIssue).filter(MaterialIssue.created_at >= today_start).count()
    )
    from services.material_auto_consumption import consumptions_today_stats

    consumption_stats = consumptions_today_stats(db)
    return {
        "low_stock": low_stock,
        "receipts_today": receipts_today,
        "issues_today": issues_today,
        "inventory_value": inventory_value,
        **consumption_stats,
    }


def _normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def _record_movement(
    db: Session,
    material: Material,
    username: str,
    *,
    movement_type: str,
    quantity: float,
    reference_type: str,
    reference_id: int,
    notes: str = "",
    unit_cost: float | None = None,
) -> MaterialStockMovement:
    movement = MaterialStockMovement(
        material_id=material.id,
        movement_type=movement_type,
        quantity=quantity,
        balance_after=float(material.quantity or 0),
        unit_cost=unit_cost if unit_cost is not None else float(material.unit_cost or 0),
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
        created_by=username,
        created_at=datetime.utcnow(),
    )
    db.add(movement)
    db.flush()
    log_value_change(
        db,
        username,
        movement_type,
        "material_stock_movement",
        movement.id,
        "quantity",
        None,
        quantity,
    )
    return movement


def list_categories(db: Session, *, include_inactive: bool = False) -> list[dict]:
    query = db.query(MaterialCategory).order_by(MaterialCategory.sort_order, MaterialCategory.name)
    if not include_inactive:
        query = query.filter(MaterialCategory.is_active.is_(True))
    return [serialize_category(c) for c in query.all()]


def create_category(
    db: Session,
    username: str,
    *,
    name: str,
    code: str = "",
    description: str = "",
    sort_order: int = 0,
) -> dict:
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("Category name is required")
    clean_code = _normalize_code(code) if code else None
    if clean_code:
        dup = db.query(MaterialCategory).filter(MaterialCategory.code == clean_code).first()
        if dup:
            raise ValueError("Category code already exists")
    cat = MaterialCategory(
        name=clean_name,
        code=clean_code,
        description=(description or "").strip(),
        sort_order=sort_order,
        is_active=True,
    )
    db.add(cat)
    db.flush()
    log_value_change(db, username, "create", "material_category", cat.id, "name", None, clean_name)
    return serialize_category(cat)


def update_category(
    db: Session,
    cat: MaterialCategory,
    username: str,
    *,
    name: str | None = None,
    code: str | None = None,
    description: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
) -> dict:
    if name is not None:
        clean = name.strip()
        if not clean:
            raise ValueError("Category name is required")
        if clean != cat.name:
            log_value_change(db, username, "update", "material_category", cat.id, "name", cat.name, clean)
            cat.name = clean
    if code is not None:
        clean_code = _normalize_code(code) or None
        if clean_code:
            dup = (
                db.query(MaterialCategory)
                .filter(MaterialCategory.code == clean_code, MaterialCategory.id != cat.id)
                .first()
            )
            if dup:
                raise ValueError("Category code already exists")
        if clean_code != cat.code:
            log_value_change(db, username, "update", "material_category", cat.id, "code", cat.code, clean_code)
            cat.code = clean_code
    if description is not None:
        cat.description = description.strip()
    if sort_order is not None:
        cat.sort_order = sort_order
    if is_active is not None:
        old = cat.is_active
        cat.is_active = is_active
        log_value_change(db, username, "update", "material_category", cat.id, "is_active", old, is_active)
    return serialize_category(cat)


def list_materials(db: Session, *, include_inactive: bool = False) -> list[dict]:
    query = (
        db.query(Material)
        .options(joinedload(Material.category))
        .order_by(Material.name)
    )
    if not include_inactive:
        query = query.filter(Material.is_active.is_(True))
    return [serialize_material(m) for m in query.all()]


def get_material(db: Session, material_id: int) -> Material | None:
    return (
        db.query(Material)
        .options(joinedload(Material.category))
        .filter(Material.id == material_id)
        .first()
    )


def create_material(
    db: Session,
    username: str,
    *,
    code: str,
    name: str,
    unit: str = "dona",
    category_id: int | None = None,
    minimum_stock: float = 0,
    current_stock: float = 0,
    unit_cost: float = 0,
) -> dict:
    clean_code = _normalize_code(code)
    clean_name = (name or "").strip()
    if not clean_code:
        raise ValueError("Material code is required")
    if not clean_name:
        raise ValueError("Material name is required")
    if db.query(Material).filter(Material.code == clean_code).first():
        raise ValueError("Material code already exists")
    if db.query(Material).filter(Material.name == clean_name).first():
        raise ValueError("Material name already exists")
    if category_id:
        cat = db.query(MaterialCategory).filter(MaterialCategory.id == category_id).first()
        if not cat:
            raise ValueError("Category not found")

    now = datetime.utcnow()
    mat = Material(
        code=clean_code,
        name=clean_name,
        unit=(unit or "dona").strip(),
        category_id=category_id,
        quantity=max(0.0, float(current_stock)),
        min_quantity=max(0.0, float(minimum_stock)),
        unit_cost=max(0.0, float(unit_cost)),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(mat)
    db.flush()
    log_value_change(db, username, "create", "material", mat.id, "code", None, clean_code)
    return serialize_material(mat)


def update_material(
    db: Session,
    mat: Material,
    username: str,
    *,
    code: str | None = None,
    name: str | None = None,
    unit: str | None = None,
    category_id: int | None = None,
    minimum_stock: float | None = None,
    unit_cost: float | None = None,
    is_active: bool | None = None,
) -> dict:
    if code is not None:
        clean = _normalize_code(code)
        if not clean:
            raise ValueError("Material code is required")
        dup = db.query(Material).filter(Material.code == clean, Material.id != mat.id).first()
        if dup:
            raise ValueError("Material code already exists")
        if clean != mat.code:
            log_value_change(db, username, "update", "material", mat.id, "code", mat.code, clean)
            mat.code = clean
    if name is not None:
        clean = name.strip()
        if not clean:
            raise ValueError("Material name is required")
        dup = db.query(Material).filter(Material.name == clean, Material.id != mat.id).first()
        if dup:
            raise ValueError("Material name already exists")
        if clean != mat.name:
            log_value_change(db, username, "update", "material", mat.id, "name", mat.name, clean)
            mat.name = clean
    if unit is not None:
        mat.unit = unit.strip() or mat.unit
    if category_id is not None:
        if category_id:
            cat = db.query(MaterialCategory).filter(MaterialCategory.id == category_id).first()
            if not cat:
                raise ValueError("Category not found")
        mat.category_id = category_id or None
    if minimum_stock is not None:
        old = float(mat.min_quantity or 0)
        mat.min_quantity = max(0.0, float(minimum_stock))
        if old != mat.min_quantity:
            log_value_change(
                db, username, "update", "material", mat.id, "min_quantity", old, mat.min_quantity
            )
    if unit_cost is not None:
        old = float(mat.unit_cost or 0)
        mat.unit_cost = max(0.0, float(unit_cost))
        if old != mat.unit_cost:
            log_value_change(db, username, "update", "material", mat.id, "unit_cost", old, mat.unit_cost)
    if is_active is not None:
        old = mat.is_active
        mat.is_active = is_active
        log_value_change(db, username, "update", "material", mat.id, "is_active", old, is_active)
    mat.updated_at = datetime.utcnow()
    db.refresh(mat, attribute_names=["category"])
    return serialize_material(mat)


def create_receipt(
    db: Session,
    username: str,
    *,
    material_id: int,
    quantity: float,
    unit_cost: float | None = None,
    reference: str = "",
    notes: str = "",
) -> dict:
    qty = float(quantity)
    if qty <= 0:
        raise ValueError("Quantity must be positive")
    mat = get_material(db, material_id)
    if not mat or not mat.is_active:
        raise ValueError("Material not found")

    cost = max(0.0, float(unit_cost)) if unit_cost is not None else float(mat.unit_cost or 0)
    receipt = MaterialReceipt(
        material_id=mat.id,
        quantity=qty,
        unit_cost=cost,
        reference=(reference or "").strip(),
        notes=(notes or "").strip(),
        created_by=username,
        created_at=datetime.utcnow(),
    )
    db.add(receipt)
    db.flush()

    old_qty = float(mat.quantity or 0)
    mat.quantity = old_qty + qty
    if unit_cost is not None:
        mat.unit_cost = cost
    mat.updated_at = datetime.utcnow()
    log_value_change(db, username, "receipt", "material", mat.id, "quantity", old_qty, mat.quantity)

    _record_movement(
        db,
        mat,
        username,
        movement_type="receipt",
        quantity=qty,
        reference_type="receipt",
        reference_id=receipt.id,
        notes=notes,
        unit_cost=cost,
    )
    return {
        "receipt_id": receipt.id,
        "material": serialize_material(mat),
    }


def create_issue(
    db: Session,
    username: str,
    *,
    material_id: int,
    quantity: float,
    reason: str = "",
    reference: str = "",
    notes: str = "",
) -> dict:
    qty = float(quantity)
    if qty <= 0:
        raise ValueError("Quantity must be positive")
    mat = get_material(db, material_id)
    if not mat or not mat.is_active:
        raise ValueError("Material not found")
    if float(mat.quantity or 0) < qty:
        raise ValueError("Insufficient stock")

    issue = MaterialIssue(
        material_id=mat.id,
        quantity=qty,
        reason=(reason or "").strip(),
        reference=(reference or "").strip(),
        notes=(notes or "").strip(),
        created_by=username,
        created_at=datetime.utcnow(),
    )
    db.add(issue)
    db.flush()

    old_qty = float(mat.quantity or 0)
    mat.quantity = old_qty - qty
    mat.updated_at = datetime.utcnow()
    log_value_change(db, username, "issue", "material", mat.id, "quantity", old_qty, mat.quantity)

    movement = _record_movement(
        db,
        mat,
        username,
        movement_type="issue",
        quantity=qty,
        reference_type="issue",
        reference_id=issue.id,
        notes=notes or reason,
    )
    return {
        "issue_id": issue.id,
        "movement_id": movement.id,
        "material": serialize_material(mat),
    }


def create_adjustment(
    db: Session,
    username: str,
    *,
    material_id: int,
    quantity_after: float,
    reason: str = "",
    notes: str = "",
) -> dict:
    mat = get_material(db, material_id)
    if not mat or not mat.is_active:
        raise ValueError("Material not found")
    new_qty = max(0.0, float(quantity_after))
    old_qty = float(mat.quantity or 0)
    delta = new_qty - old_qty
    if abs(delta) < 0.0001:
        raise ValueError("No adjustment needed")

    adj = MaterialAdjustment(
        material_id=mat.id,
        quantity_before=old_qty,
        quantity_after=new_qty,
        adjustment_delta=delta,
        reason=(reason or "").strip(),
        notes=(notes or "").strip(),
        created_by=username,
        created_at=datetime.utcnow(),
    )
    db.add(adj)
    db.flush()

    mat.quantity = new_qty
    mat.updated_at = datetime.utcnow()
    log_value_change(db, username, "adjustment", "material", mat.id, "quantity", old_qty, new_qty)

    _record_movement(
        db,
        mat,
        username,
        movement_type="adjustment",
        quantity=abs(delta),
        reference_type="adjustment",
        reference_id=adj.id,
        notes=notes or reason,
    )
    return {
        "adjustment_id": adj.id,
        "material": serialize_material(mat),
    }


def list_receipts(db: Session, limit: int = 100) -> list[dict]:
    rows = (
        db.query(MaterialReceipt)
        .options(joinedload(MaterialReceipt.material).joinedload(Material.category))
        .order_by(MaterialReceipt.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "material_id": r.material_id,
            "material_code": r.material.code if r.material else "",
            "material_name": r.material.name if r.material else "",
            "quantity": float(r.quantity),
            "unit_cost": float(r.unit_cost or 0),
            "reference": r.reference or "",
            "notes": r.notes or "",
            "created_by": r.created_by,
            "created_at": r.created_at,
        }
        for r in rows
    ]


def list_issues(db: Session, limit: int = 100) -> list[dict]:
    rows = (
        db.query(MaterialIssue)
        .options(joinedload(MaterialIssue.material))
        .order_by(MaterialIssue.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": i.id,
            "material_id": i.material_id,
            "material_code": i.material.code if i.material else "",
            "material_name": i.material.name if i.material else "",
            "quantity": float(i.quantity),
            "reason": i.reason or "",
            "reference": i.reference or "",
            "notes": i.notes or "",
            "created_by": i.created_by,
            "created_at": i.created_at,
        }
        for i in rows
    ]


def list_adjustments(db: Session, limit: int = 100) -> list[dict]:
    rows = (
        db.query(MaterialAdjustment)
        .options(joinedload(MaterialAdjustment.material))
        .order_by(MaterialAdjustment.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": a.id,
            "material_id": a.material_id,
            "material_code": a.material.code if a.material else "",
            "material_name": a.material.name if a.material else "",
            "quantity_before": float(a.quantity_before),
            "quantity_after": float(a.quantity_after),
            "adjustment_delta": float(a.adjustment_delta),
            "reason": a.reason or "",
            "notes": a.notes or "",
            "created_by": a.created_by,
            "created_at": a.created_at,
        }
        for a in rows
    ]


def list_movements(db: Session, limit: int = 200) -> list[dict]:
    rows = (
        db.query(MaterialStockMovement)
        .options(joinedload(MaterialStockMovement.material))
        .order_by(MaterialStockMovement.created_at.desc())
        .limit(limit)
        .all()
    )
    return [serialize_movement(m) for m in rows]
