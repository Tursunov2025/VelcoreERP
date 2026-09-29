"""Raw materials warehouse (P4-A1)."""

from __future__ import annotations

from datetime import datetime, time
import json
import math
from uuid import uuid4

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from models import (
    Material,
    MaterialAdjustment,
    MaterialCategory,
    MaterialIssue,
    MaterialReceipt,
    MaterialStockLengthLot,
    MaterialStockPiece,
    MaterialStockMovement,
)
from services.audit import log_value_change

DEFAULT_CATEGORIES = [
    ("METAL", "Metall"),
    ("SHEET", "List materiallar"),
    ("WIRE", "Simlar"),
    ("WOOD", "Yog'och asosli materiallar"),
    ("PLASTIC", "Plastmassa va akril"),
    ("PAINT", "Bo'yoq"),
    ("FASTENER", "Mahkamlash elementlari"),
    ("HARDWARE", "Furnitura"),
    ("PACKAGING", "Qadoqlash materiallari"),
    ("CONS", "Sarf materiallar"),
]

MATERIAL_TYPES = {
    "PROFILE",
    "SHEET_METAL",
    "STEEL_WIRE",
    "LAMINATE",
    "PLYWOOD",
    "PLASTIC",
    "ACRYLIC",
    "MDF",
    "CHIPBOARD",
    "LAMINATED_CHIPBOARD",
    "PAINT",
    "WELDING_CONSUMABLE",
    "FASTENER",
    "HARDWARE",
    "RUBBER_PVC",
    "PACKAGING",
    "CONSUMABLE",
}
SHEET_LIKE_TYPES = {
    "SHEET_METAL",
    "LAMINATE",
    "PLYWOOD",
    "PLASTIC",
    "ACRYLIC",
    "MDF",
    "CHIPBOARD",
    "LAMINATED_CHIPBOARD",
    "RUBBER_PVC",
}
PROFILE_TYPES = {"SQUARE", "RECTANGULAR", "ROUND_TUBE", "ANGLE", "U_PROFILE", "C_PROFILE", "Z_PROFILE"}
VALID_UNITS = {"m", "metr", "dona", "pcs", "kg", "l", "m2"}
STEEL_DENSITY_KG_M3 = 7850.0


class MaterialWarehouseError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _fail(code: str, message: str, status_code: int = 400) -> None:
    raise MaterialWarehouseError(code, message, status_code)


def _positive(value, field: str, *, required: bool = False) -> float | None:
    if value in (None, ""):
        if required:
            _fail("material_dimension_required", f"{field} is required")
        return None
    number = float(value)
    if number <= 0:
        _fail("material_dimension_positive", f"{field} must be positive")
    return number


def _fmt_dimension(value: float) -> str:
    return f"{float(value):g}"


def generate_material_code(
    *, material_type: str, profile_type: str | None = None, width_mm=None,
    height_mm=None, diameter_mm=None, thickness_mm=None,
) -> str:
    kind = str(material_type or "").strip().upper()
    profile = str(profile_type or "").strip().upper()
    if kind != "PROFILE" or profile not in PROFILE_TYPES:
        _fail("material_auto_code_unavailable", "Automatic code is available for profile materials")
    thickness = _positive(thickness_mm, "thickness_mm", required=True)
    prefixes = {
        "SQUARE": "SQ", "RECTANGULAR": "RT", "ROUND_TUBE": "RD", "ANGLE": "AN",
        "U_PROFILE": "UP", "C_PROFILE": "CP", "Z_PROFILE": "ZP",
    }
    if profile == "ROUND_TUBE":
        diameter = _positive(diameter_mm, "diameter_mm", required=True)
        dimensions = f"{_fmt_dimension(diameter)}x{_fmt_dimension(thickness)}"
    else:
        width = _positive(width_mm, "width_mm", required=True)
        height = _positive(height_mm, "height_mm", required=True)
        dimensions = f"{_fmt_dimension(width)}x{_fmt_dimension(height)}x{_fmt_dimension(thickness)}"
    return f"PR-{prefixes[profile]}-{dimensions}".upper()


def _material_geometry(data: dict) -> dict:
    material_type = str(data.get("material_type") or "CONSUMABLE").strip().upper()
    if material_type not in MATERIAL_TYPES:
        _fail("material_type_invalid", "Unsupported material type")
    profile_type = str(data.get("profile_type") or "").strip().upper() or None
    values = {
        "material_type": material_type,
        "profile_type": profile_type,
        "width_mm": None, "height_mm": None, "diameter_mm": None,
        "thickness_mm": None, "inner_radius_mm": None, "length_mm": None,
        "density_kg_m3": None, "theoretical_weight_kg_per_m": None,
    }
    if material_type == "PROFILE":
        if profile_type not in PROFILE_TYPES:
            _fail("profile_type_required", "Select a supported profile type")
        values["thickness_mm"] = _positive(data.get("thickness_mm"), "thickness_mm", required=True)
        if profile_type == "ROUND_TUBE":
            values["diameter_mm"] = _positive(data.get("diameter_mm"), "diameter_mm", required=True)
            if values["thickness_mm"] * 2 >= values["diameter_mm"]:
                _fail("profile_geometry_invalid", "Thickness must be less than the profile radius")
        else:
            values["width_mm"] = _positive(data.get("width_mm"), "width_mm", required=True)
            values["height_mm"] = _positive(data.get("height_mm"), "height_mm", required=True)
            if profile_type == "SQUARE" and abs(values["width_mm"] - values["height_mm"]) > 0.0001:
                _fail("profile_square_dimensions", "Square profile width and height must match")
            if values["thickness_mm"] * 2 >= min(values["width_mm"], values["height_mm"]):
                _fail("profile_geometry_invalid", "Thickness is invalid for these profile dimensions")
        values["inner_radius_mm"] = _positive(data.get("inner_radius_mm"), "inner_radius_mm")
        values["density_kg_m3"] = STEEL_DENSITY_KG_M3
        t = values["thickness_mm"]
        if profile_type in {"SQUARE", "RECTANGULAR"}:
            b, h = values["width_mm"], values["height_mm"]
            area_mm2 = b * h - (b - 2 * t) * (h - 2 * t)
        elif profile_type == "ROUND_TUBE":
            d = values["diameter_mm"]
            area_mm2 = math.pi / 4 * (d * d - (d - 2 * t) ** 2)
        elif profile_type == "ANGLE":
            area_mm2 = t * (values["width_mm"] + values["height_mm"] - t)
        else:
            area_mm2 = None
        if area_mm2:
            values["theoretical_weight_kg_per_m"] = round(area_mm2 * 0.00785, 4)
    elif material_type in SHEET_LIKE_TYPES:
        values["width_mm"] = _positive(data.get("width_mm"), "width_mm", required=True)
        values["length_mm"] = _positive(data.get("length_mm"), "length_mm", required=True)
        values["thickness_mm"] = _positive(data.get("thickness_mm"), "thickness_mm", required=True)
    if material_type == "SHEET_METAL":
        values["density_kg_m3"] = STEEL_DENSITY_KG_M3

    elif material_type == "STEEL_WIRE":
        values["diameter_mm"] = _positive(
        data.get("diameter_mm"),
        "diameter_mm",
        required=True,
    )
    values["density_kg_m3"] = STEEL_DENSITY_KG_M3

    return values


def _validate_units(material_type: str, unit: str, purchase_unit: str) -> tuple[str, str]:
    base = str(unit or "").strip().lower()
    purchase = str(purchase_unit or "").strip().lower()
    if base not in VALID_UNITS or purchase not in VALID_UNITS:
        _fail("material_unit_invalid", "Select supported base and purchase units")
    if material_type == "PROFILE" and (base not in {"m", "metr"} or purchase not in {"pcs", "dona"}):
        _fail("profile_units_invalid", "Profiles use metres as base unit and pieces as purchase unit")
    return ("m" if base == "metr" else base), ("pcs" if purchase == "dona" and material_type == "PROFILE" else purchase)


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


def serialize_length_lot(row: MaterialStockLengthLot) -> dict:
    return {
        "id": row.id,
        "material_id": row.material_id,
        "receipt_id": row.receipt_id,
        "receipt_document_id": getattr(row, "receipt_document_id", None),
        "length_m": float(row.length_m),
        "pieces_on_hand": int(row.pieces_on_hand),
        "pieces_reserved": int(row.pieces_reserved or 0),
        "pieces_available": int(row.pieces_on_hand - (row.pieces_reserved or 0)),
        "available_meters": round(
            float(row.length_m) * int(row.pieces_on_hand - (row.pieces_reserved or 0)), 6,
        ),
        "total_meters": float(row.total_meters or 0),
        "pieces_received": int(getattr(row, "pieces_received", 0) or row.pieces_on_hand or 0),
        "meters_received": float(getattr(row, "meters_received", 0) or row.total_meters or 0),
        "status": getattr(row, "status", "ACTIVE") or "ACTIVE",
        "warehouse_name": row.warehouse_name or "",
        "location_code": row.location_code or "",
        "lot_number": row.lot_number or "",
        "supplier_name": getattr(row, "supplier_name", "") or "",
        "supplier_invoice": getattr(row, "supplier_invoice", "") or "",
        "source_reference": row.source_reference or "",
        "notes": row.notes or "",
        "unit_cost": float(row.unit_cost or 0),
        "version": row.version,
        "created_by": row.created_by,
        "created_at": row.created_at,
    }


def serialize_material(mat: Material) -> dict:
    qty = float(mat.quantity or 0)
    min_stock = float(mat.min_quantity or 0)
    unit_cost = float(mat.unit_cost or 0)
    length_lots = sorted(mat.length_lots or [], key=lambda row: (row.length_m, row.id))
    total_pieces = sum(int(row.pieces_on_hand or 0) for row in length_lots)
    lot_total_meters = round(sum(float(row.total_meters or 0) for row in length_lots), 4)
    sheet_area_m2 = None
    sheet_weight_kg = None
    if mat.material_type == "SHEET_METAL" and mat.width_mm and mat.length_mm:
        sheet_area_m2 = round(float(mat.width_mm) * float(mat.length_mm) / 1_000_000, 6)
        if mat.thickness_mm and mat.density_kg_m3:
            sheet_weight_kg = round(
                sheet_area_m2 * float(mat.thickness_mm) / 1000 * float(mat.density_kg_m3), 4,
            )
    return {
        "id": mat.id,
        "code": mat.code or "",
        "name": mat.name,
        "unit": mat.unit or "dona",
        "base_unit": mat.unit or "dona",
        "purchase_unit": mat.purchase_unit or "dona",
        "material_type": mat.material_type or "CONSUMABLE",
        "profile_type": mat.profile_type,
        "steel_grade": mat.steel_grade or "",
        "description": mat.description or "",
        "image_url": mat.image_url or "",
        "width_mm": mat.width_mm,
        "height_mm": mat.height_mm,
        "diameter_mm": mat.diameter_mm,
        "thickness_mm": mat.thickness_mm,
        "inner_radius_mm": mat.inner_radius_mm,
        "length_mm": mat.length_mm,
        "density_kg_m3": mat.density_kg_m3,
        "theoretical_weight_kg_per_m": mat.theoretical_weight_kg_per_m,
        "sheet_area_m2": sheet_area_m2,
        "sheet_weight_kg": sheet_weight_kg,
        "category_id": mat.category_id,
        "category_name": mat.category.name if mat.category else "",
        "minimum_stock": min_stock,
        "current_stock": qty,
        "unit_cost": unit_cost,
        "inventory_value": round(qty * unit_cost, 2),
        "low_stock": qty <= min_stock,
        "is_active": bool(mat.is_active),
        "length_lots": [serialize_length_lot(row) for row in length_lots],
        "length_lot_summary": {
            "total_pieces": total_pieces,
            "total_meters": lot_total_meters,
            "lengths_m": sorted({float(row.length_m) for row in length_lots}),
        },
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
        .options(joinedload(Material.category), joinedload(Material.length_lots))
        .order_by(Material.name)
    )
    if not include_inactive:
        query = query.filter(Material.is_active.is_(True))
    return [serialize_material(m) for m in query.all()]


def get_material(db: Session, material_id: int) -> Material | None:
    return (
        db.query(Material)
        .options(joinedload(Material.category), joinedload(Material.length_lots))
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
    purchase_unit: str = "dona",
    material_type: str = "CONSUMABLE",
    profile_type: str | None = None,
    category_id: int | None = None,
    minimum_stock: float = 0,
    current_stock: float = 0,
    unit_cost: float = 0,
    steel_grade: str = "",
    description: str = "",
    width_mm: float | None = None,
    height_mm: float | None = None,
    diameter_mm: float | None = None,
    thickness_mm: float | None = None,
    inner_radius_mm: float | None = None,
    length_mm: float | None = None,
    density_kg_m3: float | None = None,
    auto_code: bool = False,
    initial_length_lots: list[dict] | None = None,
    is_active: bool = True,
) -> dict:
    geometry = _material_geometry({
        "material_type": material_type, "profile_type": profile_type,
        "width_mm": width_mm, "height_mm": height_mm, "diameter_mm": diameter_mm,
        "thickness_mm": thickness_mm, "inner_radius_mm": inner_radius_mm,
        "length_mm": length_mm, "density_kg_m3": density_kg_m3,
    })
    base_unit, clean_purchase_unit = _validate_units(geometry["material_type"], unit, purchase_unit)
    clean_code = _normalize_code(generate_material_code(
        material_type=geometry["material_type"], profile_type=geometry["profile_type"],
        width_mm=geometry["width_mm"], height_mm=geometry["height_mm"],
        diameter_mm=geometry["diameter_mm"], thickness_mm=geometry["thickness_mm"],
    ) if auto_code else code)
    clean_name = (name or "").strip()
    if not clean_code:
        _fail("material_code_required", "Material code is required")
    if not clean_name:
        _fail("material_name_required", "Material name is required")
    if db.query(Material).filter(Material.code == clean_code).first():
        _fail("material_code_exists", "Material code already exists")
    if db.query(Material).filter(Material.name == clean_name).first():
        _fail("material_name_exists", "Material name already exists")
    if category_id:
        cat = db.query(MaterialCategory).filter(MaterialCategory.id == category_id).first()
        if not cat:
            _fail("material_category_not_found", "Category not found")

    minimum = float(minimum_stock)
    stock = float(current_stock)
    cost = float(unit_cost)
    if min(minimum, stock, cost) < 0:
        _fail("material_quantity_nonnegative", "Stock, minimum stock and unit cost cannot be negative")
    lots = list(initial_length_lots or [])
    if geometry["material_type"] == "PROFILE" and stock > 0:
        _fail("profile_stock_requires_lot", "Profile opening stock requires physical length lots")

    now = datetime.utcnow()
    mat = Material(
        code=clean_code,
        name=clean_name,
        unit=base_unit,
        purchase_unit=clean_purchase_unit,
        material_type=geometry["material_type"],
        profile_type=geometry["profile_type"],
        steel_grade=(steel_grade or "").strip(),
        description=(description or "").strip(),
        width_mm=geometry["width_mm"], height_mm=geometry["height_mm"],
        diameter_mm=geometry["diameter_mm"], thickness_mm=geometry["thickness_mm"],
        inner_radius_mm=geometry["inner_radius_mm"], length_mm=geometry["length_mm"],
        theoretical_weight_kg_per_m=geometry["theoretical_weight_kg_per_m"],
        density_kg_m3=geometry["density_kg_m3"],
        category_id=category_id,
        quantity=stock,
        min_quantity=minimum,
        unit_cost=cost,
        is_active=bool(is_active),
        created_at=now,
        updated_at=now,
    )
    db.add(mat)
    db.flush()
    log_value_change(db, username, "create", "material", mat.id, "code", None, clean_code)
    for lot in lots:
        create_receipt(
            db, username, material_id=mat.id, quantity=lot.get("total_meters"),
            unit_cost=lot.get("unit_cost", cost), reference=lot.get("source_reference", ""),
            notes=lot.get("notes", ""), length_m=lot.get("length_m"),
            piece_count=lot.get("piece_count", lot.get("pieces_on_hand")),
            warehouse_name=lot.get("warehouse_name", ""),
            location_code=lot.get("location_code", ""), lot_number=lot.get("lot_number", ""),
        )
    db.refresh(mat, attribute_names=["category", "length_lots"])
    return serialize_material(mat)


def update_material(
    db: Session,
    mat: Material,
    username: str,
    *,
    code: str | None = None,
    name: str | None = None,
    unit: str | None = None,
    purchase_unit: str | None = None,
    material_type: str | None = None,
    profile_type: str | None = None,
    category_id: int | None = None,
    minimum_stock: float | None = None,
    unit_cost: float | None = None,
    is_active: bool | None = None,
    steel_grade: str | None = None,
    description: str | None = None,
    width_mm: float | None = None,
    height_mm: float | None = None,
    diameter_mm: float | None = None,
    thickness_mm: float | None = None,
    inner_radius_mm: float | None = None,
    length_mm: float | None = None,
    new_length_lots: list[dict] | None = None,
) -> dict:
    if code is not None:
        clean = _normalize_code(code)
        if not clean:
            _fail("material_code_required", "Material code is required")
        dup = db.query(Material).filter(Material.code == clean, Material.id != mat.id).first()
        if dup:
            _fail("material_code_exists", "Material code already exists")
        if clean != mat.code:
            log_value_change(db, username, "update", "material", mat.id, "code", mat.code, clean)
            mat.code = clean
    if name is not None:
        clean = name.strip()
        if not clean:
            _fail("material_name_required", "Material name is required")
        dup = db.query(Material).filter(Material.name == clean, Material.id != mat.id).first()
        if dup:
            _fail("material_name_exists", "Material name already exists")
        if clean != mat.name:
            log_value_change(db, username, "update", "material", mat.id, "name", mat.name, clean)
            mat.name = clean
    if material_type is not None:
        geometry = _material_geometry({
            "material_type": material_type, "profile_type": profile_type,
            "width_mm": width_mm, "height_mm": height_mm, "diameter_mm": diameter_mm,
            "thickness_mm": thickness_mm, "inner_radius_mm": inner_radius_mm,
            "length_mm": length_mm,
        })
        base_unit, clean_purchase = _validate_units(
            geometry["material_type"], unit or mat.unit, purchase_unit or mat.purchase_unit,
        )
        mat.unit = base_unit; mat.purchase_unit = clean_purchase
        for field, value in geometry.items():
            setattr(mat, field, value)
    else:
        if unit is not None or purchase_unit is not None:
            base_unit, clean_purchase = _validate_units(
                mat.material_type or "CONSUMABLE", unit or mat.unit, purchase_unit or mat.purchase_unit,
            )
            mat.unit = base_unit; mat.purchase_unit = clean_purchase
    if steel_grade is not None: mat.steel_grade = steel_grade.strip()
    if description is not None: mat.description = description.strip()
    if category_id is not None:
        if category_id:
            cat = db.query(MaterialCategory).filter(MaterialCategory.id == category_id).first()
            if not cat:
                _fail("material_category_not_found", "Category not found")
        mat.category_id = category_id or None
    if minimum_stock is not None:
        old = float(mat.min_quantity or 0)
        if float(minimum_stock) < 0: _fail("material_quantity_nonnegative", "Minimum stock cannot be negative")
        mat.min_quantity = float(minimum_stock)
        if old != mat.min_quantity:
            log_value_change(
                db, username, "update", "material", mat.id, "min_quantity", old, mat.min_quantity
            )
    if unit_cost is not None:
        old = float(mat.unit_cost or 0)
        if float(unit_cost) < 0: _fail("material_quantity_nonnegative", "Unit cost cannot be negative")
        mat.unit_cost = float(unit_cost)
        if old != mat.unit_cost:
            log_value_change(db, username, "update", "material", mat.id, "unit_cost", old, mat.unit_cost)
    if is_active is not None:
        old = mat.is_active
        mat.is_active = is_active
        log_value_change(db, username, "update", "material", mat.id, "is_active", old, is_active)
    mat.updated_at = datetime.utcnow()
    for lot in list(new_length_lots or []):
        create_receipt(
            db, username, material_id=mat.id, quantity=lot.get("total_meters"),
            unit_cost=lot.get("unit_cost", mat.unit_cost), reference=lot.get("source_reference", ""),
            notes=lot.get("notes", ""), length_m=lot.get("length_m"),
            piece_count=lot.get("piece_count", lot.get("pieces_on_hand")),
            warehouse_name=lot.get("warehouse_name", ""),
            location_code=lot.get("location_code", ""), lot_number=lot.get("lot_number", ""),
        )
    db.refresh(mat, attribute_names=["category", "length_lots"])
    return serialize_material(mat)


def _whole_pieces(value) -> int:
    try:
        pieces = int(value)
    except (TypeError, ValueError):
        _fail("material_piece_count_positive", "Piece count must be a positive whole number")
    if pieces <= 0 or float(value) != pieces:
        _fail("material_piece_count_positive", "Piece count must be a positive whole number")
    return pieces


def _receipt_profile_rows(
    mat: Material,
    *,
    profile_rows: list[dict] | None,
    length_m: float | None,
    piece_count: int | None,
    quantity: float | None,
    unit_cost: float | None,
    price_basis: str,
    warehouse_name: str,
    location_code: str,
    lot_number: str,
    notes: str,
) -> list[dict]:
    source_rows = list(profile_rows or [])
    professional_rows = bool(source_rows)
    if not source_rows and (length_m not in (None, "") or piece_count not in (None, "")):
        source_rows = [{
            "length_m": length_m, "piece_count": piece_count, "unit_cost": unit_cost,
            "warehouse_name": warehouse_name, "location_code": location_code,
            "lot_number": lot_number, "notes": notes, "price_basis": price_basis,
        }]
    if not source_rows:
        _fail("material_receipt_rows_required", "Add at least one physical length row")

    normalized = []
    for row in source_rows:
        bar_length = _positive(row.get("length_m"), "length_m", required=True)
        pieces = _whole_pieces(row.get("piece_count", row.get("pieces")))
        total_meters = round(bar_length * pieces, 6)
        basis = str(row.get("price_basis") or price_basis or "PER_METER").strip().upper()
        if basis == "PER_UNIT":
            # Backward-compatible profile receipts historically expressed
            # ``unit_cost`` in the canonical base unit (metres).
            basis = "PER_METER"
        if basis not in {"PER_METER", "PER_PIECE"}:
            _fail("material_price_basis_invalid", "Select price per metre or per piece")
        entered_cost = row.get("unit_cost", unit_cost)
        entered_cost = float(entered_cost if entered_cost not in (None, "") else mat.unit_cost or 0)
        if entered_cost < 0:
            _fail("material_cost_nonnegative", "Cost cannot be negative")
        price_per_meter = entered_cost if basis == "PER_METER" else entered_cost / bar_length
        row_total = round(
            total_meters * price_per_meter if basis == "PER_METER" else pieces * entered_cost,
            2,
        )
        theoretical = float(mat.theoretical_weight_kg_per_m) if mat.theoretical_weight_kg_per_m else None
        row_warehouse = str(row.get("warehouse_name") or warehouse_name or "").strip()
        row_location = str(row.get("location_code") or location_code or "").strip()
        if professional_rows and not row_warehouse:
            _fail("material_receipt_warehouse_required", "Warehouse is required for each physical row")
        if professional_rows and not row_location:
            _fail("material_receipt_location_required", "Location is required for each physical row")
        normalized.append({
            "length_m": bar_length,
            "piece_count": pieces,
            "total_meters": total_meters,
            "price_basis": basis,
            "entered_cost": entered_cost,
            "price_per_meter": round(price_per_meter, 6),
            "row_total": row_total,
            "theoretical_weight_kg_per_m": theoretical,
            "total_weight_kg": round(total_meters * theoretical, 4) if theoretical is not None else None,
            "warehouse_name": row_warehouse,
            "location_code": row_location,
            "lot_number": str(row.get("lot_number") or lot_number or "").strip(),
            "notes": str(row.get("notes") or "").strip(),
        })
    calculated = round(sum(row["total_meters"] for row in normalized), 6)
    if quantity not in (None, "") and abs(float(quantity) - calculated) > 0.0001:
        _fail("material_conversion_invalid", "Profile metres must equal length multiplied by pieces")
    return normalized


def _receipt_lots(db: Session, receipt_id: int) -> list[MaterialStockLengthLot]:
    return (
        db.query(MaterialStockLengthLot)
        .filter(or_(
            MaterialStockLengthLot.receipt_document_id == receipt_id,
            MaterialStockLengthLot.receipt_id == receipt_id,
        ))
        .order_by(MaterialStockLengthLot.length_m, MaterialStockLengthLot.id)
        .all()
    )


def _receipt_payload(db: Session, receipt: MaterialReceipt, *, idempotent: bool = False) -> dict:
    lots = _receipt_lots(db, receipt.id)
    mat = receipt.material or get_material(db, receipt.material_id)
    try:
        profile_rows = json.loads(receipt.profile_rows_json or "[]")
    except (TypeError, ValueError):
        profile_rows = []
    return {
        "id": receipt.id,
        "receipt_id": receipt.id,
        "receipt_number": receipt.receipt_number or f"MR-{receipt.id:06d}",
        "material_id": receipt.material_id,
        "material_code": mat.code if mat else "",
        "material_name": mat.name if mat else "",
        "material_type": mat.material_type if mat else "",
        "category_name": mat.category.name if mat and mat.category else "",
        "quantity": float(receipt.quantity or 0),
        "total_pieces": int(receipt.total_pieces or 0),
        "total_weight_kg": float(receipt.total_weight_kg) if receipt.total_weight_kg is not None else None,
        "total_amount": float(receipt.total_amount or 0),
        "unit_cost": float(receipt.unit_cost or 0),
        "price_basis": receipt.price_basis or "PER_UNIT",
        "currency": receipt.currency or "UZS",
        "base_unit": receipt.base_unit or (mat.unit if mat else ""),
        "purchase_unit": receipt.purchase_unit or (mat.purchase_unit if mat else ""),
        "supplier_name": receipt.supplier_name or "",
        "supplier_invoice": receipt.supplier_invoice or "",
        "warehouse_name": receipt.warehouse_name or "",
        "location_code": receipt.location_code or "",
        "lot_number": receipt.lot_number or "",
        "reference": receipt.reference or "",
        "notes": receipt.notes or "",
        "status": receipt.status or "CONFIRMED",
        "stock_applied": bool(receipt.stock_applied),
        "version": int(receipt.version or 1),
        "profile_rows": profile_rows,
        "length_lots": [serialize_length_lot(row) for row in lots],
        "length_lot": serialize_length_lot(lots[0]) if len(lots) == 1 else None,
        "created_by": receipt.created_by,
        "created_at": receipt.created_at,
        "received_at": receipt.received_at or receipt.created_at,
        "confirmed_by": receipt.confirmed_by,
        "confirmed_at": receipt.confirmed_at,
        "reversed_by": receipt.reversed_by,
        "reversed_at": receipt.reversed_at,
        "reversal_reason": receipt.reversal_reason or "",
        "idempotent": idempotent,
        "material": serialize_material(mat) if mat else None,
    }


def create_receipt(
    db: Session,
    username: str,
    *,
    material_id: int,
    quantity: float | None,
    unit_cost: float | None = None,
    reference: str = "",
    notes: str = "",
    length_m: float | None = None,
    piece_count: int | None = None,
    warehouse_name: str = "",
    location_code: str = "",
    lot_number: str = "",
    profile_rows: list[dict] | None = None,
    receipt_number: str = "",
    supplier_name: str = "",
    supplier_invoice: str = "",
    received_at: datetime | None = None,
    price_basis: str = "PER_UNIT",
    currency: str = "UZS",
    operation_key: str = "",
    confirm: bool = True,
) -> dict:
    mat = get_material(db, material_id)
    if not mat or not mat.is_active:
        _fail("material_not_found", "Material not found")
    clean_key = (operation_key or "").strip() or f"receipt-{uuid4().hex}"
    existing = db.query(MaterialReceipt).filter(MaterialReceipt.operation_key == clean_key).first()
    if existing:
        if existing.material_id != mat.id:
            _fail("material_receipt_idempotency_conflict", "Operation key belongs to another receipt", 409)
        return _receipt_payload(db, existing, idempotent=True)

    kind = (mat.material_type or "CONSUMABLE").upper()
    rows: list[dict] = []
    if kind == "PROFILE":
        rows = _receipt_profile_rows(
            mat, profile_rows=profile_rows, length_m=length_m, piece_count=piece_count,
            quantity=quantity, unit_cost=unit_cost, price_basis=price_basis,
            warehouse_name=warehouse_name, location_code=location_code,
            lot_number=lot_number, notes=notes,
        )
        qty = round(sum(row["total_meters"] for row in rows), 6)
        total_pieces = sum(row["piece_count"] for row in rows)
        total_amount = round(sum(row["row_total"] for row in rows), 2)
        weights = [row["total_weight_kg"] for row in rows]
        total_weight = round(sum(weights), 4) if weights and all(v is not None for v in weights) else None
        cost = round(total_amount / qty, 6) if qty else 0.0
        normalized_basis = rows[0]["price_basis"] if rows else "PER_METER"
    else:
        if profile_rows or length_m not in (None, "") or piece_count not in (None, ""):
            _fail("material_length_lot_not_applicable", "Physical length lots apply only to profile materials")
        if quantity in (None, ""):
            _fail("material_quantity_positive", "Quantity is required")
        qty = float(quantity)
        if qty <= 0:
            _fail("material_quantity_positive", "Quantity must be positive")
        cost = float(unit_cost) if unit_cost not in (None, "") else float(mat.unit_cost or 0)
        if cost < 0:
            _fail("material_cost_nonnegative", "Cost cannot be negative")
        total_pieces = 0
        total_weight = None
        total_amount = round(qty * cost, 2)
        normalized_basis = "PER_UNIT"

    clean_number = (receipt_number or "").strip()
    if clean_number and db.query(MaterialReceipt).filter(MaterialReceipt.receipt_number == clean_number).first():
        _fail("material_receipt_number_exists", "Receipt number already exists", 409)
    now = datetime.utcnow()
    receipt = MaterialReceipt(
        material_id=mat.id, quantity=qty, unit_cost=cost,
        reference=(reference or "").strip(), notes=(notes or "").strip(),
        receipt_number=clean_number or None, operation_key=clean_key,
        status="DRAFT", supplier_name=(supplier_name or "").strip(),
        supplier_invoice=(supplier_invoice or "").strip(),
        warehouse_name=(warehouse_name or "").strip(), location_code=(location_code or "").strip(),
        lot_number=(lot_number or "").strip(), purchase_unit=mat.purchase_unit or "",
        base_unit=mat.unit or "", price_basis=normalized_basis,
        currency=(currency or "UZS").strip().upper(), total_pieces=total_pieces,
        total_weight_kg=total_weight, total_amount=total_amount,
        profile_rows_json=json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
        stock_applied=False, version=1, received_at=received_at or now,
        created_by=username, created_at=now,
    )
    db.add(receipt)
    db.flush()
    if not receipt.receipt_number:
        receipt.receipt_number = f"MR-{receipt.id:06d}"
    log_value_change(db, username, "create", "material_receipt", receipt.id, "status", None, "DRAFT")
    log_value_change(db, username, "create", "material_receipt", receipt.id, "profile_rows", None, receipt.profile_rows_json)
    log_value_change(db, username, "create", "material_receipt", receipt.id, "source", None, receipt.supplier_invoice or receipt.reference or receipt.supplier_name)
    if confirm:
        return confirm_receipt(db, username, receipt.id, operation_key=clean_key)
    return _receipt_payload(db, receipt)


def update_receipt_draft(
    db: Session,
    username: str,
    receipt_id: int,
    *,
    expected_version: int,
    material_id: int,
    quantity: float | None,
    unit_cost: float | None = None,
    reference: str = "",
    notes: str = "",
    warehouse_name: str = "",
    location_code: str = "",
    lot_number: str = "",
    profile_rows: list[dict] | None = None,
    receipt_number: str = "",
    supplier_name: str = "",
    supplier_invoice: str = "",
    received_at: datetime | None = None,
    price_basis: str = "PER_UNIT",
    currency: str = "UZS",
) -> dict:
    receipt = db.query(MaterialReceipt).filter(MaterialReceipt.id == receipt_id).first()
    if not receipt:
        _fail("material_receipt_not_found", "Receipt not found", 404)
    if receipt.status != "DRAFT" or receipt.stock_applied:
        _fail("material_receipt_state_conflict", "Only draft receipts are editable", 409)
    if int(receipt.version or 1) != int(expected_version):
        _fail("material_receipt_version_conflict", "Receipt changed in another session", 409)
    mat = get_material(db, material_id)
    if not mat or not mat.is_active:
        _fail("material_not_found", "Material not found")
    clean_number = (receipt_number or "").strip()
    duplicate = db.query(MaterialReceipt).filter(
        MaterialReceipt.receipt_number == clean_number, MaterialReceipt.id != receipt.id,
    ).first() if clean_number else None
    if duplicate:
        _fail("material_receipt_number_exists", "Receipt number already exists", 409)
    kind = (mat.material_type or "CONSUMABLE").upper()
    rows: list[dict] = []
    if kind == "PROFILE":
        rows = _receipt_profile_rows(
            mat, profile_rows=profile_rows, length_m=None, piece_count=None,
            quantity=quantity, unit_cost=unit_cost, price_basis=price_basis,
            warehouse_name=warehouse_name, location_code=location_code,
            lot_number=lot_number, notes=notes,
        )
        qty = round(sum(row["total_meters"] for row in rows), 6)
        total_pieces = sum(row["piece_count"] for row in rows)
        total_amount = round(sum(row["row_total"] for row in rows), 2)
        weights = [row["total_weight_kg"] for row in rows]
        total_weight = round(sum(weights), 4) if weights and all(v is not None for v in weights) else None
        cost = round(total_amount / qty, 6) if qty else 0.0
        normalized_basis = rows[0]["price_basis"]
    else:
        if profile_rows:
            _fail("material_length_lot_not_applicable", "Physical length lots apply only to profile materials")
        qty = float(quantity or 0)
        if qty <= 0:
            _fail("material_quantity_positive", "Quantity must be positive")
        cost = float(unit_cost or 0)
        if cost < 0:
            _fail("material_cost_nonnegative", "Cost cannot be negative")
        total_pieces = 0; total_weight = None; total_amount = round(qty * cost, 2)
        normalized_basis = "PER_UNIT"
    receipt.material_id = mat.id
    receipt.quantity = qty
    receipt.unit_cost = cost
    receipt.receipt_number = clean_number or f"MR-{receipt.id:06d}"
    receipt.reference = (reference or "").strip()
    receipt.notes = (notes or "").strip()
    receipt.supplier_name = (supplier_name or "").strip()
    receipt.supplier_invoice = (supplier_invoice or "").strip()
    receipt.warehouse_name = (warehouse_name or "").strip()
    receipt.location_code = (location_code or "").strip()
    receipt.lot_number = (lot_number or "").strip()
    receipt.purchase_unit = mat.purchase_unit or ""
    receipt.base_unit = mat.unit or ""
    receipt.price_basis = normalized_basis
    receipt.currency = (currency or "UZS").strip().upper()
    receipt.total_pieces = total_pieces
    receipt.total_weight_kg = total_weight
    receipt.total_amount = total_amount
    receipt.profile_rows_json = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    receipt.received_at = received_at or receipt.received_at or datetime.utcnow()
    receipt.version = int(receipt.version or 1) + 1
    log_value_change(db, username, "update", "material_receipt", receipt.id, "version", expected_version, receipt.version)
    return _receipt_payload(db, receipt)


def confirm_receipt(db: Session, username: str, receipt_id: int, *, operation_key: str) -> dict:
    receipt = db.query(MaterialReceipt).filter(MaterialReceipt.id == receipt_id).first()
    if not receipt:
        _fail("material_receipt_not_found", "Receipt not found", 404)
    clean_key = (operation_key or "").strip()
    if not clean_key:
        _fail("material_receipt_operation_key_required", "Operation key is required")
    if receipt.status == "CONFIRMED":
        return _receipt_payload(db, receipt, idempotent=True)
    if receipt.status in {"REVERSED", "CANCELLED"}:
        _fail("material_receipt_state_conflict", "Receipt cannot be confirmed in its current state", 409)
    reused = db.query(MaterialReceipt).filter(
        MaterialReceipt.confirm_key == clean_key, MaterialReceipt.id != receipt.id,
    ).first()
    if reused:
        _fail("material_receipt_idempotency_conflict", "Operation key belongs to another receipt", 409)
    mat = get_material(db, receipt.material_id)
    if not mat or not mat.is_active:
        _fail("material_not_found", "Material not found")
    try:
        rows = json.loads(receipt.profile_rows_json or "[]")
    except (TypeError, ValueError):
        rows = []
    now = datetime.utcnow()
    lots = []
    if (mat.material_type or "").upper() == "PROFILE":
        if not rows:
            _fail("material_receipt_rows_required", "Add at least one physical length row")
        for row in rows:
            lot = MaterialStockLengthLot(
                material_id=mat.id, receipt_document_id=receipt.id,
                length_m=row["length_m"], pieces_on_hand=row["piece_count"], pieces_reserved=0,
                total_meters=row["total_meters"], pieces_received=row["piece_count"],
                meters_received=row["total_meters"], status="ACTIVE",
                warehouse_name=row.get("warehouse_name") or receipt.warehouse_name or "",
                location_code=row.get("location_code") or receipt.location_code or "",
                lot_number=row.get("lot_number") or receipt.lot_number or "",
                supplier_name=receipt.supplier_name or "", supplier_invoice=receipt.supplier_invoice or "",
                source_reference=receipt.reference or receipt.receipt_number or "",
                notes=row.get("notes") or receipt.notes or "",
                unit_cost=row.get("price_per_meter", receipt.unit_cost or 0),
                created_by=username, created_at=now, updated_at=now,
            )
            db.add(lot)
            db.flush()
            # New confirmed profile receipts receive explicit physical-piece
            # identities. Historical aggregate lots remain lazy and are never
            # exploded automatically during migration/startup.
            from services.material_cutting import materialize_lot
            materialize_lot(db, lot.id, username, f"receipt-piece-{receipt.id}-{lot.id}")
            lots.append(lot)
            log_value_change(
                db, username, "receipt", "material_stock_length_lot", lot.id,
                "total_meters", None, row["total_meters"],
            )

    old_qty = float(mat.quantity or 0)
    mat.quantity = round(old_qty + float(receipt.quantity or 0), 6)
    mat.unit_cost = float(receipt.unit_cost or mat.unit_cost or 0)
    mat.updated_at = now
    receipt.status = "CONFIRMED"
    receipt.stock_applied = True
    receipt.confirm_key = clean_key
    receipt.confirmed_at = now
    receipt.confirmed_by = username
    receipt.version = int(receipt.version or 1) + 1
    log_value_change(db, username, "receipt", "material", mat.id, "quantity", old_qty, mat.quantity)
    log_value_change(db, username, "confirm", "material_receipt", receipt.id, "status", "DRAFT", "CONFIRMED")
    log_value_change(db, username, "confirm", "material_receipt", receipt.id, "stock_effect", None, receipt.quantity)
    _record_movement(
        db, mat, username, movement_type="receipt", quantity=float(receipt.quantity or 0),
        reference_type="receipt", reference_id=receipt.id,
        notes=receipt.notes or receipt.receipt_number or "", unit_cost=receipt.unit_cost,
    )
    if lots:
        db.expire(mat, ["length_lots"])
    return _receipt_payload(db, receipt)


def reverse_receipt(
    db: Session, username: str, receipt_id: int, *, reason: str, operation_key: str,
) -> dict:
    receipt = db.query(MaterialReceipt).filter(MaterialReceipt.id == receipt_id).first()
    if not receipt:
        _fail("material_receipt_not_found", "Receipt not found", 404)
    clean_key = (operation_key or "").strip()
    clean_reason = (reason or "").strip()
    if not clean_key:
        _fail("material_receipt_operation_key_required", "Operation key is required")
    if not clean_reason:
        _fail("material_receipt_reversal_reason_required", "Reversal reason is required")
    if receipt.status in {"REVERSED", "CANCELLED"}:
        return _receipt_payload(db, receipt, idempotent=True)
    if receipt.status == "DRAFT":
        receipt.status = "CANCELLED"
        receipt.reverse_key = clean_key
        receipt.reversal_reason = clean_reason
        receipt.reversed_by = username
        receipt.reversed_at = datetime.utcnow()
        receipt.version = int(receipt.version or 1) + 1
        log_value_change(db, username, "cancel", "material_receipt", receipt.id, "status", "DRAFT", "CANCELLED")
        return _receipt_payload(db, receipt)
    if receipt.status != "CONFIRMED" or not receipt.stock_applied:
        _fail("material_receipt_state_conflict", "Receipt cannot be reversed in its current state", 409)
    reused = db.query(MaterialReceipt).filter(
        MaterialReceipt.reverse_key == clean_key, MaterialReceipt.id != receipt.id,
    ).first()
    if reused:
        _fail("material_receipt_idempotency_conflict", "Operation key belongs to another receipt", 409)

    mat = get_material(db, receipt.material_id)
    lots = _receipt_lots(db, receipt.id)
    for lot in lots:
        received_pieces = int(lot.pieces_received or lot.pieces_on_hand or 0)
        received_meters = float(lot.meters_received or lot.total_meters or 0)
        if int(lot.pieces_reserved or 0) > 0:
            _fail("material_receipt_reversal_reserved", "Reserved physical stock must be released before reversal", 409)
        if int(lot.pieces_on_hand or 0) < received_pieces or float(lot.total_meters or 0) + 0.0001 < received_meters:
            _fail("material_receipt_reversal_consumed", "Consumed physical stock cannot be reversed", 409)
        physical = db.query(MaterialStockPiece).filter_by(source_length_lot_id=lot.id).all()
        if any(p.status != "AVAILABLE" or p.parent_piece_id is not None for p in physical):
            _fail("material_receipt_reversal_consumed", "Consumed physical stock cannot be reversed", 409)
    qty = float(receipt.quantity or 0)
    if not mat or float(mat.quantity or 0) + 0.0001 < qty:
        _fail("material_receipt_reversal_stock_insufficient", "Current stock is insufficient for reversal", 409)

    now = datetime.utcnow()
    for lot in lots:
        received_pieces = int(lot.pieces_received or lot.pieces_on_hand or 0)
        received_meters = float(lot.meters_received or lot.total_meters or 0)
        lot.pieces_on_hand -= received_pieces
        lot.total_meters = round(float(lot.total_meters or 0) - received_meters, 6)
        lot.status = "REVERSED"
        lot.version = int(lot.version or 1) + 1
        lot.updated_at = now
        db.query(MaterialStockPiece).filter_by(source_length_lot_id=lot.id).delete(synchronize_session=False)
        log_value_change(db, username, "reverse", "material_stock_length_lot", lot.id, "total_meters", received_meters, lot.total_meters)
    old_qty = float(mat.quantity or 0)
    mat.quantity = round(old_qty - qty, 6)
    mat.updated_at = now
    receipt.status = "REVERSED"
    receipt.stock_applied = False
    receipt.reverse_key = clean_key
    receipt.reversal_reason = clean_reason
    receipt.reversed_by = username
    receipt.reversed_at = now
    receipt.version = int(receipt.version or 1) + 1
    log_value_change(db, username, "reverse", "material", mat.id, "quantity", old_qty, mat.quantity)
    log_value_change(db, username, "reverse", "material_receipt", receipt.id, "status", "CONFIRMED", "REVERSED")
    log_value_change(db, username, "reverse", "material_receipt", receipt.id, "reason", None, clean_reason)
    _record_movement(
        db, mat, username, movement_type="receipt_reversal", quantity=qty,
        reference_type="receipt", reference_id=receipt.id,
        notes=clean_reason, unit_cost=receipt.unit_cost,
    )
    if lots:
        db.expire(mat, ["length_lots"])
    return _receipt_payload(db, receipt)


def create_issue(
    db: Session,
    username: str,
    *,
    material_id: int,
    quantity: float,
    reason: str = "",
    reference: str = "",
    notes: str = "",
    job_id: int | None = None,
    project_id: int | None = None,
    project_line_id: int | None = None,
    release_snapshot_id: int | None = None,
    material_reservation_id: int | None = None,
    source_material_bom_line_id: int | None = None,
    source_job_bom_line_id: int | None = None,
    planned_required_quantity: float | None = None,
    operation_stage: str | None = None,
    warehouse_name: str = "",
    responsible_employee: str = "",
    operation_key: str | None = None,
    document_number: str | None = None,
) -> dict:
    qty = float(quantity)
    if qty <= 0:
        raise ValueError("Quantity must be positive")
    mat = get_material(db, material_id)
    if not mat or not mat.is_active:
        raise ValueError("Material not found")
    if float(mat.quantity or 0) < qty:
        raise ValueError("Insufficient stock")

    now = datetime.utcnow()

    issue = MaterialIssue(
        material_id=mat.id,
        quantity=qty,
        reason=(reason or "").strip(),
        reference=(reference or "").strip(),
        notes=(notes or "").strip(),
        created_by=username,
        created_at=now,
        job_id=job_id,
        project_id=project_id,
        project_line_id=project_line_id,
        release_snapshot_id=release_snapshot_id,
        material_reservation_id=material_reservation_id,
        source_material_bom_line_id=source_material_bom_line_id,
        source_job_bom_line_id=source_job_bom_line_id,
        planned_required_quantity=(
            float(planned_required_quantity)
            if planned_required_quantity is not None
            else qty
        ),
        operation_stage=operation_stage if operation_stage else None,
        warehouse_name=(warehouse_name or "").strip(),
        responsible_employee=(responsible_employee or "").strip(),
        operation_key=operation_key,
        document_number=document_number,
        issued_at=now,
        completed_at=now,
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
    return [_receipt_payload(db, row) for row in rows]


def get_receipt(db: Session, receipt_id: int) -> dict | None:
    row = (
        db.query(MaterialReceipt)
        .options(joinedload(MaterialReceipt.material).joinedload(Material.category))
        .filter(MaterialReceipt.id == receipt_id)
        .first()
    )
    return _receipt_payload(db, row) if row else None


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
