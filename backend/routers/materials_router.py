from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import MaterialCategory, MaterialConsumptionRule, MesProductPart, User
from services.material_auto_consumption import (
    create_consumption_rule,
    job_material_cost,
    list_consumption_rules,
    list_consumptions_today,
    list_job_consumptions,
    update_consumption_rule,
)
from services.settings_runtime import get_auto_consume_stages
from services.material_consumption import (
    add_part_material_bom_line,
    get_part_material_bom_line,
    list_job_reservations,
    list_part_material_bom,
    list_parts_with_material_bom,
    planning_dashboard,
    update_part_material_bom_line,
)
from services.materials_warehouse import (
    create_adjustment,
    create_category,
    create_issue,
    create_material,
    create_receipt,
    dashboard_stats,
    get_material,
    list_adjustments,
    list_categories,
    list_issues,
    list_materials,
    list_movements,
    list_receipts,
    update_category,
    update_material,
)
from services.permissions import user_has_permission

router = APIRouter(prefix="/materials", tags=["materials"])


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1)
    code: str = ""
    description: str = ""
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    code: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class MaterialCreate(BaseModel):
    code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    unit: str = "dona"
    category_id: Optional[int] = None
    minimum_stock: float = 0
    current_stock: float = 0
    unit_cost: float = 0


class MaterialUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1)
    name: Optional[str] = Field(None, min_length=1)
    unit: Optional[str] = None
    category_id: Optional[int] = None
    minimum_stock: Optional[float] = None
    unit_cost: Optional[float] = None
    is_active: Optional[bool] = None


class ReceiptCreate(BaseModel):
    material_id: int
    quantity: float = Field(..., gt=0)
    unit_cost: Optional[float] = None
    reference: str = ""
    notes: str = ""


class IssueCreate(BaseModel):
    material_id: int
    quantity: float = Field(..., gt=0)
    reason: str = ""
    reference: str = ""
    notes: str = ""


class AdjustmentCreate(BaseModel):
    material_id: int
    quantity_after: float = Field(..., ge=0)
    reason: str = ""
    notes: str = ""


class PartMaterialBomCreate(BaseModel):
    material_id: int
    quantity_per_part: float = Field(..., gt=0)


class PartMaterialBomUpdate(BaseModel):
    quantity_per_part: Optional[float] = Field(None, gt=0)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class ConsumptionRuleCreate(BaseModel):
    material_id: int
    consuming_stage: str = Field(..., min_length=1)


class ConsumptionRuleUpdate(BaseModel):
    is_active: Optional[bool] = None


def _require_view(db: Session, user: User) -> None:
    if user.role == "admin" or user_has_permission(db, user, "materials_view"):
        return
    raise HTTPException(status_code=403, detail="Permission required: materials_view")


def _require_edit(db: Session, user: User) -> None:
    if user.role == "admin" or user_has_permission(db, user, "materials_edit"):
        return
    raise HTTPException(status_code=403, detail="Permission required: materials_edit")


def _value_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/dashboard")
def materials_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    stats = dashboard_stats(db)
    planning = planning_dashboard(db)
    return {
        **stats,
        "shortage_count": planning["shortage_count"],
        "materials_planned": planning["materials_planned"],
        "total_required": planning["total_required"],
    }


@router.get("/categories")
def get_categories(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    return {"categories": list_categories(db, include_inactive=include_inactive)}


@router.post("/categories")
def post_category(
    body: CategoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_edit(db, user)
    try:
        cat = create_category(
            db,
            user.username,
            name=body.name,
            code=body.code,
            description=body.description,
            sort_order=body.sort_order,
        )
        db.commit()
        return cat
    except ValueError as e:
        raise _value_error(e) from e


@router.put("/categories/{category_id}")
def put_category(
    category_id: int,
    body: CategoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_edit(db, user)
    cat = db.query(MaterialCategory).filter(MaterialCategory.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    try:
        result = update_category(
            db,
            cat,
            user.username,
            name=body.name,
            code=body.code,
            description=body.description,
            sort_order=body.sort_order,
            is_active=body.is_active,
        )
        db.commit()
        return result
    except ValueError as e:
        raise _value_error(e) from e


@router.get("/items")
def get_materials(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    return {"materials": list_materials(db, include_inactive=include_inactive)}


@router.get("/items/{material_id}")
def get_material_item(
    material_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    mat = get_material(db, material_id)
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    from services.materials_warehouse import serialize_material

    return serialize_material(mat)


@router.post("/items")
def post_material(
    body: MaterialCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_edit(db, user)
    try:
        mat = create_material(
            db,
            user.username,
            code=body.code,
            name=body.name,
            unit=body.unit,
            category_id=body.category_id,
            minimum_stock=body.minimum_stock,
            current_stock=body.current_stock,
            unit_cost=body.unit_cost,
        )
        db.commit()
        return mat
    except ValueError as e:
        raise _value_error(e) from e


@router.put("/items/{material_id}")
def put_material(
    material_id: int,
    body: MaterialUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_edit(db, user)
    mat = get_material(db, material_id)
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    try:
        result = update_material(
            db,
            mat,
            user.username,
            code=body.code,
            name=body.name,
            unit=body.unit,
            category_id=body.category_id,
            minimum_stock=body.minimum_stock,
            unit_cost=body.unit_cost,
            is_active=body.is_active,
        )
        db.commit()
        return result
    except ValueError as e:
        raise _value_error(e) from e


@router.get("/receipts")
def get_receipts(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    return {"receipts": list_receipts(db, limit=limit)}


@router.post("/receipts")
def post_receipt(
    body: ReceiptCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_edit(db, user)
    try:
        result = create_receipt(
            db,
            user.username,
            material_id=body.material_id,
            quantity=body.quantity,
            unit_cost=body.unit_cost,
            reference=body.reference,
            notes=body.notes,
        )
        db.commit()
        return result
    except ValueError as e:
        raise _value_error(e) from e


@router.get("/issues")
def get_issues(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    return {"issues": list_issues(db, limit=limit)}


@router.post("/issues")
def post_issue(
    body: IssueCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_edit(db, user)
    try:
        result = create_issue(
            db,
            user.username,
            material_id=body.material_id,
            quantity=body.quantity,
            reason=body.reason,
            reference=body.reference,
            notes=body.notes,
        )
        db.commit()
        return result
    except ValueError as e:
        raise _value_error(e) from e


@router.get("/adjustments")
def get_adjustments(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    return {"adjustments": list_adjustments(db, limit=limit)}


@router.post("/adjustments")
def post_adjustment(
    body: AdjustmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_edit(db, user)
    try:
        result = create_adjustment(
            db,
            user.username,
            material_id=body.material_id,
            quantity_after=body.quantity_after,
            reason=body.reason,
            notes=body.notes,
        )
        db.commit()
        return result
    except ValueError as e:
        raise _value_error(e) from e


@router.get("/movements")
def get_movements(
    limit: int = 200,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    return {"movements": list_movements(db, limit=limit)}


@router.get("/planning/shortages")
def get_planning_shortages(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    return planning_dashboard(db)


@router.get("/planning/parts")
def get_parts_with_material_bom(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    return {"parts": list_parts_with_material_bom(db)}


@router.get("/jobs/{job_id}/reservations")
def get_job_material_reservations(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    return {"reservations": list_job_reservations(db, job_id)}


@router.get("/parts/{part_id}/bom")
def get_part_material_bom(
    part_id: int,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    try:
        lines = list_part_material_bom(db, part_id, include_inactive=include_inactive)
        part = db.query(MesProductPart).filter(MesProductPart.id == part_id).first()
        if not part:
            raise HTTPException(status_code=404, detail="Part not found")
        return {
            "part": {
                "id": part.id,
                "part_number": part.part_number,
                "name": part.name,
                "unit": part.unit,
            },
            "lines": lines,
        }
    except ValueError as e:
        raise _value_error(e) from e


@router.post("/parts/{part_id}/bom")
def post_part_material_bom(
    part_id: int,
    body: PartMaterialBomCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_edit(db, user)
    try:
        line = add_part_material_bom_line(
            db,
            user.username,
            part_id=part_id,
            material_id=body.material_id,
            quantity_per_part=body.quantity_per_part,
        )
        db.commit()
        return line
    except ValueError as e:
        raise _value_error(e) from e


@router.put("/parts/{part_id}/bom/{line_id}")
def put_part_material_bom(
    part_id: int,
    line_id: int,
    body: PartMaterialBomUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_edit(db, user)
    line = get_part_material_bom_line(db, part_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Material BOM line not found")
    try:
        result = update_part_material_bom_line(
            db,
            line,
            user.username,
            quantity_per_part=body.quantity_per_part,
            sort_order=body.sort_order,
            is_active=body.is_active,
        )
        db.commit()
        return result
    except ValueError as e:
        raise _value_error(e) from e


@router.delete("/parts/{part_id}/bom/{line_id}")
def delete_part_material_bom(
    part_id: int,
    line_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_edit(db, user)
    line = get_part_material_bom_line(db, part_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Material BOM line not found")
    result = update_part_material_bom_line(
        db, line, user.username, is_active=False
    )
    db.commit()
    return result


@router.get("/consumption-rules")
def get_consumption_rules(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    return {
        "stages": list(get_auto_consume_stages(db)),
        "rules": list_consumption_rules(db, include_inactive=include_inactive),
    }


@router.post("/consumption-rules")
def post_consumption_rule(
    body: ConsumptionRuleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_edit(db, user)
    try:
        rule = create_consumption_rule(
            db,
            user.username,
            material_id=body.material_id,
            consuming_stage=body.consuming_stage,
        )
        db.commit()
        return rule
    except ValueError as e:
        raise _value_error(e) from e


@router.put("/consumption-rules/{rule_id}")
def put_consumption_rule(
    rule_id: int,
    body: ConsumptionRuleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_edit(db, user)
    rule = db.query(MaterialConsumptionRule).filter(MaterialConsumptionRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Consumption rule not found")
    try:
        result = update_consumption_rule(db, rule, user.username, is_active=body.is_active)
        db.commit()
        return result
    except ValueError as e:
        raise _value_error(e) from e


@router.get("/consumptions/today")
def get_consumptions_today(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    return {"consumptions": list_consumptions_today(db, limit=limit)}


@router.get("/jobs/{job_id}/consumptions")
def get_job_consumptions(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    return {"consumptions": list_job_consumptions(db, job_id)}


@router.get("/jobs/{job_id}/material-cost")
def get_job_material_cost(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    try:
        return job_material_cost(db, job_id)
    except ValueError as e:
        raise _value_error(e) from e
