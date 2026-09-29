from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import Material, MaterialCategory, MaterialConsumptionRule, MesProductPart, User
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
    confirm_receipt,
    dashboard_stats,
    get_material,
    get_receipt,
    generate_material_code,
    list_adjustments,
    list_categories,
    list_issues,
    list_materials,
    list_movements,
    list_receipts,
    reverse_receipt,
    update_category,
    update_material,
    update_receipt_draft,
)
from services.material_cutting import (create_issue_document, create_issue_from_requirement,
    cutting_context, issue_payload, issue_reserved, job_material_requirements,
    list_pieces, materialize_lot, recommend, record_cut, release_reservation, reserve_piece)
from models import MaterialIssue
from services.permissions import user_has_permission
from services.material_images import save_material_image

router = APIRouter(prefix="/materials", tags=["materials"])

MAX_MATERIAL_IMAGE_SIZE = 5 * 1024 * 1024


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
    code: str = ""
    name: str = Field(..., min_length=1)
    unit: str = "dona"
    purchase_unit: str = "dona"
    material_type: str = "CONSUMABLE"
    profile_type: Optional[str] = None
    category_id: Optional[int] = None
    minimum_stock: float = Field(default=0, ge=0)
    current_stock: float = Field(default=0, ge=0)
    unit_cost: float = Field(default=0, ge=0)
    steel_grade: str = ""
    description: str = ""
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    diameter_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    inner_radius_mm: Optional[float] = None
    length_mm: Optional[float] = None
    auto_code: bool = False
    is_active: bool = True
    initial_length_lots: list[dict] = Field(default_factory=list)


class MaterialUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1)
    name: Optional[str] = Field(None, min_length=1)
    unit: Optional[str] = None
    purchase_unit: Optional[str] = None
    material_type: Optional[str] = None
    profile_type: Optional[str] = None
    category_id: Optional[int] = None
    minimum_stock: Optional[float] = Field(None, ge=0)
    unit_cost: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None
    steel_grade: Optional[str] = None
    description: Optional[str] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    diameter_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    inner_radius_mm: Optional[float] = None
    length_mm: Optional[float] = None
    new_length_lots: list[dict] = Field(default_factory=list)


class ProfileReceiptRow(BaseModel):
    length_m: float = Field(..., gt=0)
    piece_count: int = Field(..., gt=0)
    unit_cost: Optional[float] = Field(None, ge=0)
    price_basis: str = "PER_METER"
    warehouse_name: str = ""
    location_code: str = ""
    lot_number: str = ""
    notes: str = ""


class ReceiptCreate(BaseModel):
    material_id: int
    quantity: Optional[float] = Field(None, gt=0)
    unit_cost: Optional[float] = Field(None, ge=0)
    reference: str = ""
    notes: str = ""
    length_m: Optional[float] = Field(None, gt=0)
    piece_count: Optional[int] = Field(None, gt=0)
    warehouse_name: str = ""
    location_code: str = ""
    lot_number: str = ""
    profile_rows: list[ProfileReceiptRow] = Field(default_factory=list)
    receipt_number: str = ""
    supplier_name: str = ""
    supplier_invoice: str = ""
    received_at: Optional[datetime] = None
    price_basis: str = "PER_UNIT"
    currency: str = "UZS"
    operation_key: str = ""
    confirm: bool = True


class ReceiptConfirm(BaseModel):
    operation_key: str = Field(..., min_length=8, max_length=180)


class ReceiptReverse(BaseModel):
    operation_key: str = Field(..., min_length=8, max_length=180)
    reason: str = Field(..., min_length=1, max_length=1000)


class ReceiptUpdate(ReceiptCreate):
    expected_version: int = Field(..., ge=1)
    confirm: bool = False


class IssueCreate(BaseModel):
    material_id: int
    quantity: float = Field(..., gt=0)
    reason: str = ""
    reference: str = ""
    notes: str = ""


class PhysicalIssueCreate(BaseModel):
    material_id: int
    quantity: float = Field(..., gt=0)
    document_number: str = ""
    operation_key: str = Field(..., min_length=8, max_length=180)
    project_id: Optional[int] = None
    project_line_id: Optional[int] = None
    job_id: Optional[int] = None
    operation_stage: str = "LAZER"
    warehouse_name: str = ""
    responsible_employee: str = ""
    reason: str = ""
    reference: str = ""
    notes: str = ""


class PieceReserve(BaseModel):
    piece_id: int
    expected_version: int = Field(..., ge=1)


class CutCreate(BaseModel):
    piece_id: int
    actual_cut_length_m: float = Field(..., gt=0)
    planned_cut_length_m: Optional[float] = Field(None, gt=0)
    kerf_m: Optional[float] = Field(None, ge=0)
    operation_key: str = Field(..., min_length=8, max_length=180)


class RecommendationRequest(BaseModel):
    material_id: int
    cuts: list[float] = Field(..., min_length=1)
    kerf_m: float = Field(default=.003, ge=0)


class RequirementIssueCreate(BaseModel):
    job_id: int
    source_job_bom_line_id: int
    source_material_bom_line_id: int
    operation_key: str = Field(..., min_length=8, max_length=180)


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
    return HTTPException(status_code=getattr(exc, "status_code", 400), detail={
        "code": getattr(exc, "code", "material_validation_failed"),
        "message": str(exc),
    })


@router.get("/code-preview")
def material_code_preview(
    material_type: str,
    profile_type: Optional[str] = None,
    width_mm: Optional[float] = None,
    height_mm: Optional[float] = None,
    diameter_mm: Optional[float] = None,
    thickness_mm: Optional[float] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    try:
        return {"code": generate_material_code(
            material_type=material_type, profile_type=profile_type, width_mm=width_mm,
            height_mm=height_mm, diameter_mm=diameter_mm, thickness_mm=thickness_mm,
        )}
    except ValueError as exc:
        raise _value_error(exc) from exc


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
            purchase_unit=body.purchase_unit,
            material_type=body.material_type,
            profile_type=body.profile_type,
            category_id=body.category_id,
            minimum_stock=body.minimum_stock,
            current_stock=body.current_stock,
            unit_cost=body.unit_cost,
            steel_grade=body.steel_grade,
            description=body.description,
            width_mm=body.width_mm, height_mm=body.height_mm,
            diameter_mm=body.diameter_mm, thickness_mm=body.thickness_mm,
            inner_radius_mm=body.inner_radius_mm, length_mm=body.length_mm,
            auto_code=body.auto_code, initial_length_lots=body.initial_length_lots,
            is_active=body.is_active,
        )
        db.commit()
        return mat
    except ValueError as e:
        raise _value_error(e) from e


@router.post("/items/{material_id}/image")
async def upload_material_image(
    material_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    file: UploadFile = File(...),
):
    _require_edit(db, user)

    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")

    content = await file.read()

    if len(content) > MAX_MATERIAL_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

    try:
        saved = save_material_image(content, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    mat.image_url = saved["url"]
    mat.updated_at = datetime.utcnow()
    db.commit()

    from services.materials_warehouse import serialize_material
    db.refresh(mat)
    return serialize_material(mat)


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
            purchase_unit=body.purchase_unit,
            material_type=body.material_type,
            profile_type=body.profile_type,
            category_id=body.category_id,
            minimum_stock=body.minimum_stock,
            unit_cost=body.unit_cost,
            is_active=body.is_active,
            steel_grade=body.steel_grade,
            description=body.description,
            width_mm=body.width_mm, height_mm=body.height_mm,
            diameter_mm=body.diameter_mm, thickness_mm=body.thickness_mm,
            inner_radius_mm=body.inner_radius_mm, length_mm=body.length_mm,
            new_length_lots=body.new_length_lots,
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


@router.get("/receipts/{receipt_id}")
def get_receipt_detail(
    receipt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_view(db, user)
    result = get_receipt(db, receipt_id)
    if not result:
        raise HTTPException(status_code=404, detail={
            "code": "material_receipt_not_found", "message": "Receipt not found",
        })
    return result


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
            length_m=body.length_m, piece_count=body.piece_count,
            warehouse_name=body.warehouse_name, location_code=body.location_code,
            lot_number=body.lot_number,
            profile_rows=[row.model_dump() for row in body.profile_rows],
            receipt_number=body.receipt_number,
            supplier_name=body.supplier_name,
            supplier_invoice=body.supplier_invoice,
            received_at=body.received_at,
            price_basis=body.price_basis,
            currency=body.currency,
            operation_key=body.operation_key,
            confirm=body.confirm,
        )
        db.commit()
        return result
    except ValueError as e:
        raise _value_error(e) from e


@router.post("/receipts/{receipt_id}/confirm")
def post_receipt_confirm(
    receipt_id: int,
    body: ReceiptConfirm,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_edit(db, user)
    try:
        result = confirm_receipt(db, user.username, receipt_id, operation_key=body.operation_key)
        db.commit()
        return result
    except ValueError as e:
        raise _value_error(e) from e


@router.put("/receipts/{receipt_id}")
def put_receipt_draft(
    receipt_id: int,
    body: ReceiptUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_edit(db, user)
    try:
        result = update_receipt_draft(
            db, user.username, receipt_id, expected_version=body.expected_version,
            material_id=body.material_id, quantity=body.quantity, unit_cost=body.unit_cost,
            reference=body.reference, notes=body.notes, warehouse_name=body.warehouse_name,
            location_code=body.location_code, lot_number=body.lot_number,
            profile_rows=[row.model_dump() for row in body.profile_rows],
            receipt_number=body.receipt_number, supplier_name=body.supplier_name,
            supplier_invoice=body.supplier_invoice, received_at=body.received_at,
            price_basis=body.price_basis, currency=body.currency,
        )
        db.commit()
        return result
    except ValueError as e:
        raise _value_error(e) from e


@router.post("/receipts/{receipt_id}/reverse")
def post_receipt_reverse(
    receipt_id: int,
    body: ReceiptReverse,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_edit(db, user)
    try:
        result = reverse_receipt(
            db, user.username, receipt_id, reason=body.reason, operation_key=body.operation_key,
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


@router.get("/physical-pieces")
def get_physical_pieces(material_id: Optional[int] = None, status: Optional[str] = None,
                        db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_view(db, user); return {"pieces": list_pieces(db, material_id, status)}


@router.get("/cutting/context")
def get_cutting_context(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_view(db, user); return cutting_context(db)


@router.get("/cutting/jobs/{job_id}/requirements")
def get_cutting_job_requirements(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_view(db, user)
    try: return job_material_requirements(db, job_id)
    except ValueError as e: raise _value_error(e) from e


@router.post("/cutting/issues")
def post_cutting_issue(body: RequirementIssueCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_edit(db, user)
    try:
        result=create_issue_from_requirement(db,user.username,body.job_id,body.source_job_bom_line_id,
            body.source_material_bom_line_id,body.operation_key); db.commit(); return result
    except ValueError as e: db.rollback(); raise _value_error(e) from e


@router.post("/length-lots/{lot_id}/materialize")
def post_materialize_lot(lot_id: int, operation_key: str,
                         db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_edit(db, user)
    try: result = materialize_lot(db, lot_id, user.username, operation_key); db.commit(); return result
    except ValueError as e: db.rollback(); raise _value_error(e) from e


@router.post("/physical-issues")
def post_physical_issue(body: PhysicalIssueCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_edit(db, user)
    try: result = create_issue_document(db, user.username, body.model_dump()); db.commit(); return result
    except ValueError as e: db.rollback(); raise _value_error(e) from e


@router.get("/physical-issues")
def get_physical_issues(limit: int = 100, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_view(db, user)
    rows = db.query(MaterialIssue).filter(MaterialIssue.operation_key.isnot(None)).order_by(MaterialIssue.created_at.desc()).limit(limit).all()
    return {"issues": [issue_payload(db, row) for row in rows]}


@router.get("/physical-issues/{issue_id}")
def get_physical_issue(issue_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_view(db, user); row = db.query(MaterialIssue).filter_by(id=issue_id).first()
    if not row: raise HTTPException(404, detail={"code":"material_issue_not_found","message":"Issue not found"})
    return issue_payload(db, row)


@router.post("/physical-issues/{issue_id}/reserve")
def post_piece_reserve(issue_id: int, body: PieceReserve, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_edit(db, user)
    try: result = reserve_piece(db, issue_id, body.piece_id, body.expected_version, user.username); db.commit(); return result
    except ValueError as e: db.rollback(); raise _value_error(e) from e


@router.post("/physical-issues/{issue_id}/release")
def post_piece_release(issue_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_edit(db, user)
    try: result = release_reservation(db, issue_id, user.username); db.commit(); return result
    except ValueError as e: db.rollback(); raise _value_error(e) from e


@router.post("/physical-issues/{issue_id}/issue")
def post_issue_reserved(issue_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_edit(db, user)
    try: result = issue_reserved(db, issue_id, user.username); db.commit(); return result
    except ValueError as e: db.rollback(); raise _value_error(e) from e


@router.post("/physical-issues/{issue_id}/cuts")
def post_cut(issue_id: int, body: CutCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_edit(db, user)
    try:
        result = record_cut(db, issue_id, body.piece_id, body.actual_cut_length_m, body.kerf_m,
                            body.operation_key, user.username, body.planned_cut_length_m)
        db.commit(); return result
    except ValueError as e: db.rollback(); raise _value_error(e) from e


@router.post("/cutting/recommend")
def post_cut_recommendation(body: RecommendationRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_view(db, user); return recommend(db, body.material_id, body.cuts, body.kerf_m)


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
