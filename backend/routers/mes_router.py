from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from auth.deps import get_current_user
from database import get_db
from models import (
    MesBomLine,
    MesProductCategory,
    MesProductDrawing,
    MesProductPart,
    MesProductTemplate,
    MesProductionRoute,
    MesProductionStage,
    MesRouteStep,
    User,
)
from services.audit import log_action
from services.mes_drawings import (
    active_drawings,
    clear_primary_drawings,
    save_drawing_file,
    serialize_drawing,
    serialize_drawings,
)
from services.mes_bom import (
    find_bom_line,
    get_active_part,
    next_sort_order,
    save_bom_drawing,
    serialize_bom,
    serialize_bom_line,
    validate_required_quantity,
)
from services.mes_routes import (
    active_route_steps,
    active_routes,
    copy_route_steps,
    get_active_route,
    next_step_order,
    serialize_route,
    serialize_route_step,
    set_default_route,
)
from services.mes_templates import (
    duplicate_template,
    save_template_image,
    serialize_template,
)
from services.permissions import user_has_permission

router = APIRouter(prefix="/mes", tags=["mes"])


class CategoryCreate(BaseModel):
    name: str
    description: str = ""
    parent_id: Optional[int] = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class PartCreate(BaseModel):
    part_number: str
    name: str
    unit: str = "dona"
    description: str = ""
    material_id: Optional[int] = None


class PartUpdate(BaseModel):
    part_number: Optional[str] = None
    name: Optional[str] = None
    unit: Optional[str] = None
    description: Optional[str] = None
    material_id: Optional[int] = None
    is_active: Optional[bool] = None


class TemplateCreate(BaseModel):
    code: str
    name: str
    category_id: Optional[int] = None
    description: str = ""
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    weight_kg: Optional[float] = None
    image_url: Optional[str] = None
    qr_prefix: Optional[str] = None
    is_active: bool = True


class TemplateUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    category_id: Optional[int] = None
    description: Optional[str] = None
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    weight_kg: Optional[float] = None
    image_url: Optional[str] = None
    qr_prefix: Optional[str] = None
    is_active: Optional[bool] = None


class TemplateDuplicate(BaseModel):
    code: str


class BomLineCreate(BaseModel):
    part_id: int
    required_quantity: float = Field(..., gt=0)
    produced_quantity: float = 0
    accepted_quantity: float = 0
    rejected_quantity: float = 0
    notes: str = ""
    drawing_url: Optional[str] = None
    sort_order: Optional[int] = None


class BomLineUpdate(BaseModel):
    required_quantity: Optional[float] = Field(None, gt=0)
    produced_quantity: Optional[float] = None
    accepted_quantity: Optional[float] = None
    rejected_quantity: Optional[float] = None
    notes: Optional[str] = None
    drawing_url: Optional[str] = None
    sort_order: Optional[int] = None


class BomReorderItem(BaseModel):
    id: int
    sort_order: int


class BomReorder(BaseModel):
    lines: list[BomReorderItem]


class StageCreate(BaseModel):
    name: str
    department: str = "Admin"
    color: Optional[str] = None
    sort_order: int = 0


class StageUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class RouteCreate(BaseModel):
    name: str
    version: int = 1
    is_default: bool = False


class RouteUpdate(BaseModel):
    name: Optional[str] = None


class RouteStepCreate(BaseModel):
    stage_id: int
    step_order: Optional[int] = None
    department: Optional[str] = None
    responsible_role: Optional[str] = None
    estimated_minutes: Optional[int] = None
    required_parts_count: int = 0
    completed_parts_count: int = 0
    instructions: str = ""
    is_required: bool = True


class RouteStepUpdate(BaseModel):
    stage_id: Optional[int] = None
    department: Optional[str] = None
    responsible_role: Optional[str] = None
    estimated_minutes: Optional[int] = None
    required_parts_count: Optional[int] = None
    completed_parts_count: Optional[int] = None
    instructions: Optional[str] = None
    is_required: Optional[bool] = None


class RouteStepReorderItem(BaseModel):
    id: int
    step_order: int


class RouteStepReorder(BaseModel):
    steps: list[RouteStepReorderItem]


class DrawingUpdate(BaseModel):
    title: Optional[str] = None
    revision: Optional[str] = None
    is_primary: Optional[bool] = None


def _normalize_template_code(value: str) -> str:
    return (value or "").strip().upper()


def _get_active_template(db: Session, template_id: int) -> MesProductTemplate:
    template = (
        db.query(MesProductTemplate)
        .options(
            joinedload(MesProductTemplate.category),
            joinedload(MesProductTemplate.bom_lines).joinedload(MesBomLine.part),
            joinedload(MesProductTemplate.routes)
            .joinedload(MesProductionRoute.steps)
            .joinedload(MesRouteStep.stage),
            joinedload(MesProductTemplate.default_route)
            .joinedload(MesProductionRoute.steps)
            .joinedload(MesRouteStep.stage),
            joinedload(MesProductTemplate.drawings),
        )
        .filter(MesProductTemplate.id == template_id)
        .first()
    )
    if not template or template.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


def _validate_category(db: Session, category_id: Optional[int]) -> None:
    if category_id is None:
        return
    cat = (
        db.query(MesProductCategory)
        .filter(
            MesProductCategory.id == category_id,
            MesProductCategory.is_active.is_(True),
        )
        .first()
    )
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")


def _require(db: Session, user: User, perm: str) -> None:
    if not user_has_permission(db, user, perm):
        raise HTTPException(status_code=403, detail=f"Permission required: {perm}")


def _require_route_design(db: Session, user: User) -> None:
    if user_has_permission(db, user, "mes_edit") or user_has_permission(
        db, user, "mes_routes_design"
    ):
        return
    raise HTTPException(status_code=403, detail="Permission required: mes_routes_design")


def _require_drawings_upload(db: Session, user: User) -> None:
    if user_has_permission(db, user, "mes_edit") or user_has_permission(
        db, user, "mes_drawings_upload"
    ):
        return
    raise HTTPException(status_code=403, detail="Permission required: mes_drawings_upload")


def _serialize_category(cat: MesProductCategory, template_count: int = 0) -> dict:
    return {
        "id": cat.id,
        "name": cat.name,
        "description": cat.description or "",
        "parent_id": cat.parent_id,
        "sort_order": cat.sort_order,
        "is_active": bool(cat.is_active),
        "created_at": cat.created_at,
        "created_by": cat.created_by,
        "template_count": template_count,
    }


def _serialize_part(part: MesProductPart) -> dict:
    return {
        "id": part.id,
        "part_number": part.part_number,
        "name": part.name,
        "unit": part.unit,
        "description": part.description or "",
        "material_id": part.material_id,
        "is_active": bool(part.is_active),
        "deleted_at": part.deleted_at,
        "created_at": part.created_at,
        "updated_at": part.updated_at,
        "created_by": part.created_by,
    }


def _normalize_part_number(value: str) -> str:
    return (value or "").strip().upper()


def _category_template_counts(db: Session, category_ids: list[int]) -> dict[int, int]:
    if not category_ids:
        return {}
    rows = (
        db.query(MesProductTemplate.category_id, MesProductTemplate.id)
        .filter(
            MesProductTemplate.category_id.in_(category_ids),
            MesProductTemplate.is_active.is_(True),
            MesProductTemplate.deleted_at.is_(None),
        )
        .all()
    )
    counts: dict[int, int] = {}
    for category_id, _ in rows:
        if category_id is not None:
            counts[category_id] = counts.get(category_id, 0) + 1
    return counts


@router.get("/categories")
def list_categories(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    include_inactive: bool = Query(False),
):
    _require(db, user, "mes_view")
    query = db.query(MesProductCategory).order_by(
        MesProductCategory.sort_order, MesProductCategory.name
    )
    if not include_inactive:
        query = query.filter(MesProductCategory.is_active.is_(True))
    categories = query.all()
    counts = _category_template_counts(db, [c.id for c in categories])
    return {
        "categories": [
            _serialize_category(c, counts.get(c.id, 0)) for c in categories
        ]
    }


@router.post("/categories")
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_edit")
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Category name required")
    if data.parent_id is not None:
        parent = (
            db.query(MesProductCategory)
            .filter(
                MesProductCategory.id == data.parent_id,
                MesProductCategory.is_active.is_(True),
            )
            .first()
        )
        if not parent:
            raise HTTPException(status_code=404, detail="Parent category not found")
    duplicate = (
        db.query(MesProductCategory)
        .filter(
            MesProductCategory.name == name,
            MesProductCategory.parent_id == data.parent_id,
            MesProductCategory.is_active.is_(True),
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Category name already exists at this level")

    category = MesProductCategory(
        name=name,
        description=data.description or "",
        parent_id=data.parent_id,
        sort_order=data.sort_order,
        created_by=user.username,
    )
    db.add(category)
    log_action(db, user.username, "create", "mes_category", details=name)
    db.commit()
    db.refresh(category)
    return _serialize_category(category)


@router.put("/categories/{category_id}")
def update_category(
    category_id: int,
    data: CategoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_edit")
    category = db.query(MesProductCategory).filter(MesProductCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if data.parent_id is not None:
        if data.parent_id == category_id:
            raise HTTPException(status_code=400, detail="Category cannot be its own parent")
        if data.parent_id:
            parent = (
                db.query(MesProductCategory)
                .filter(MesProductCategory.id == data.parent_id)
                .first()
            )
            if not parent:
                raise HTTPException(status_code=404, detail="Parent category not found")

    if data.name is not None:
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Category name required")
        category.name = name
    if data.description is not None:
        category.description = data.description
    if data.parent_id is not None:
        category.parent_id = data.parent_id or None
    if data.sort_order is not None:
        category.sort_order = data.sort_order
    if data.is_active is not None:
        category.is_active = bool(data.is_active)

    log_action(db, user.username, "update", "mes_category", category_id, category.name)
    db.commit()
    counts = _category_template_counts(db, [category.id])
    return _serialize_category(category, counts.get(category.id, 0))


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_delete")
    category = (
        db.query(MesProductCategory)
        .filter(MesProductCategory.id == category_id, MesProductCategory.is_active.is_(True))
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    child_count = (
        db.query(MesProductCategory)
        .filter(
            MesProductCategory.parent_id == category_id,
            MesProductCategory.is_active.is_(True),
        )
        .count()
    )
    if child_count:
        raise HTTPException(status_code=400, detail="Category has active subcategories")

    template_count = (
        db.query(MesProductTemplate)
        .filter(
            MesProductTemplate.category_id == category_id,
            MesProductTemplate.is_active.is_(True),
            MesProductTemplate.deleted_at.is_(None),
        )
        .count()
    )
    if template_count:
        raise HTTPException(status_code=400, detail="Category has active product templates")

    category.is_active = False
    log_action(db, user.username, "delete", "mes_category", category_id, category.name)
    db.commit()
    return {"message": "Category deactivated"}


@router.get("/parts")
def list_parts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    q: str = Query(""),
    include_inactive: bool = Query(False),
):
    _require(db, user, "mes_view")
    query = db.query(MesProductPart).order_by(MesProductPart.part_number)
    if not include_inactive:
        query = query.filter(
            MesProductPart.is_active.is_(True),
            MesProductPart.deleted_at.is_(None),
        )
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            MesProductPart.part_number.ilike(term) | MesProductPart.name.ilike(term)
        )
    parts = query.all()
    return {"parts": [_serialize_part(p) for p in parts]}


@router.get("/parts/{part_id}")
def get_part(
    part_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_view")
    part = db.query(MesProductPart).filter(MesProductPart.id == part_id).first()
    if not part or (not part.is_active and part.deleted_at):
        raise HTTPException(status_code=404, detail="Part not found")
    return _serialize_part(part)


@router.post("/parts")
def create_part(
    data: PartCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_edit")
    part_number = _normalize_part_number(data.part_number)
    name = (data.name or "").strip()
    if not part_number:
        raise HTTPException(status_code=400, detail="Part number required")
    if not name:
        raise HTTPException(status_code=400, detail="Part name required")

    existing = (
        db.query(MesProductPart)
        .filter(
            MesProductPart.part_number == part_number,
            MesProductPart.is_active.is_(True),
            MesProductPart.deleted_at.is_(None),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Part number already exists")

    part = MesProductPart(
        part_number=part_number,
        name=name,
        unit=(data.unit or "dona").strip() or "dona",
        description=data.description or "",
        material_id=data.material_id,
        created_by=user.username,
    )
    db.add(part)
    log_action(db, user.username, "create", "mes_part", details=part_number)
    db.commit()
    db.refresh(part)
    return _serialize_part(part)


@router.put("/parts/{part_id}")
def update_part(
    part_id: int,
    data: PartUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_edit")
    part = (
        db.query(MesProductPart)
        .filter(MesProductPart.id == part_id, MesProductPart.deleted_at.is_(None))
        .first()
    )
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    if data.part_number is not None:
        part_number = _normalize_part_number(data.part_number)
        if not part_number:
            raise HTTPException(status_code=400, detail="Part number required")
        clash = (
            db.query(MesProductPart)
            .filter(
                MesProductPart.part_number == part_number,
                MesProductPart.id != part_id,
                MesProductPart.is_active.is_(True),
                MesProductPart.deleted_at.is_(None),
            )
            .first()
        )
        if clash:
            raise HTTPException(status_code=400, detail="Part number already exists")
        part.part_number = part_number

    if data.name is not None:
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Part name required")
        part.name = name
    if data.unit is not None:
        part.unit = data.unit.strip() or part.unit
    if data.description is not None:
        part.description = data.description
    if data.material_id is not None:
        part.material_id = data.material_id
    if data.is_active is not None:
        part.is_active = bool(data.is_active)
        if part.is_active:
            part.deleted_at = None

    part.updated_at = datetime.utcnow()
    log_action(db, user.username, "update", "mes_part", part_id, part.part_number)
    db.commit()
    db.refresh(part)
    return _serialize_part(part)


@router.delete("/parts/{part_id}")
def delete_part(
    part_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_delete")
    part = (
        db.query(MesProductPart)
        .filter(
            MesProductPart.id == part_id,
            MesProductPart.is_active.is_(True),
            MesProductPart.deleted_at.is_(None),
        )
        .first()
    )
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    part.is_active = False
    part.deleted_at = datetime.utcnow()
    log_action(db, user.username, "delete", "mes_part", part_id, part.part_number)
    db.commit()
    return {"message": "Part deactivated"}


MAX_TEMPLATE_IMAGE_SIZE = 5 * 1024 * 1024


@router.get("/templates")
def list_templates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    q: str = Query(""),
    category_id: Optional[int] = Query(None),
    include_inactive: bool = Query(False),
):
    _require(db, user, "mes_view")
    query = (
        db.query(MesProductTemplate)
        .options(
            joinedload(MesProductTemplate.category),
            joinedload(MesProductTemplate.bom_lines).joinedload(MesBomLine.part),
            joinedload(MesProductTemplate.routes)
            .joinedload(MesProductionRoute.steps)
            .joinedload(MesRouteStep.stage),
            joinedload(MesProductTemplate.default_route)
            .joinedload(MesProductionRoute.steps)
            .joinedload(MesRouteStep.stage),
            joinedload(MesProductTemplate.drawings),
        )
        .filter(MesProductTemplate.deleted_at.is_(None))
        .order_by(MesProductTemplate.code)
    )
    if not include_inactive:
        query = query.filter(MesProductTemplate.is_active.is_(True))
    if category_id is not None:
        query = query.filter(MesProductTemplate.category_id == category_id)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            MesProductTemplate.code.ilike(term) | MesProductTemplate.name.ilike(term)
        )
    templates = query.all()
    return {"templates": [serialize_template(t) for t in templates]}


@router.get("/templates/{template_id}")
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_view")
    template = _get_active_template(db, template_id)
    return serialize_template(template)


@router.post("/templates")
def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_edit")
    code = _normalize_template_code(data.code)
    name = (data.name or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="Template code required")
    if not name:
        raise HTTPException(status_code=400, detail="Template name required")
    _validate_category(db, data.category_id)

    existing = (
        db.query(MesProductTemplate)
        .filter(
            MesProductTemplate.code == code,
            MesProductTemplate.deleted_at.is_(None),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Template code already exists")

    template = MesProductTemplate(
        code=code,
        name=name,
        category_id=data.category_id,
        description=data.description or "",
        length_mm=data.length_mm,
        width_mm=data.width_mm,
        height_mm=data.height_mm,
        weight_kg=data.weight_kg,
        image_url=data.image_url,
        qr_prefix=(data.qr_prefix or "").strip() or None,
        is_active=bool(data.is_active),
        created_by=user.username,
    )
    db.add(template)
    log_action(db, user.username, "create", "mes_template", details=code)
    db.commit()
    db.refresh(template)
    return serialize_template(_get_active_template(db, template.id))


@router.put("/templates/{template_id}")
def update_template(
    template_id: int,
    data: TemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_edit")
    template = _get_active_template(db, template_id)

    if data.code is not None:
        code = _normalize_template_code(data.code)
        if not code:
            raise HTTPException(status_code=400, detail="Template code required")
        clash = (
            db.query(MesProductTemplate)
            .filter(
                MesProductTemplate.code == code,
                MesProductTemplate.id != template_id,
                MesProductTemplate.deleted_at.is_(None),
            )
            .first()
        )
        if clash:
            raise HTTPException(status_code=400, detail="Template code already exists")
        template.code = code

    if data.name is not None:
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Template name required")
        template.name = name
    if data.category_id is not None:
        _validate_category(db, data.category_id)
        template.category_id = data.category_id
    if data.description is not None:
        template.description = data.description
    if data.length_mm is not None:
        template.length_mm = data.length_mm
    if data.width_mm is not None:
        template.width_mm = data.width_mm
    if data.height_mm is not None:
        template.height_mm = data.height_mm
    if data.weight_kg is not None:
        template.weight_kg = data.weight_kg
    if data.image_url is not None:
        template.image_url = data.image_url or None
    if data.qr_prefix is not None:
        template.qr_prefix = data.qr_prefix.strip() or None
    if data.is_active is not None:
        template.is_active = bool(data.is_active)

    template.updated_at = datetime.utcnow()
    log_action(db, user.username, "update", "mes_template", template_id, template.code)
    db.commit()
    return serialize_template(_get_active_template(db, template_id))


@router.delete("/templates/{template_id}")
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_delete")
    template = _get_active_template(db, template_id)
    template.is_active = False
    template.deleted_at = datetime.utcnow()
    log_action(db, user.username, "delete", "mes_template", template_id, template.code)
    db.commit()
    return {"message": "Template deactivated"}


@router.post("/templates/{template_id}/duplicate")
def duplicate_template_endpoint(
    template_id: int,
    data: TemplateDuplicate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_edit")
    try:
        copy = duplicate_template(db, template_id, data.code, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_action(
        db,
        user.username,
        "duplicate",
        "mes_template",
        copy.id,
        f"from {template_id} -> {copy.code}",
    )
    db.commit()
    return serialize_template(_get_active_template(db, copy.id))


@router.post("/templates/{template_id}/image")
async def upload_template_image(
    template_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    file: UploadFile = File(...),
):
    _require(db, user, "mes_edit")
    template = _get_active_template(db, template_id)
    content = await file.read()
    if len(content) > MAX_TEMPLATE_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")
    try:
        saved = save_template_image(content, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    template.image_url = saved["url"]
    template.updated_at = datetime.utcnow()
    log_action(db, user.username, "upload", "mes_template_image", template_id, template.code)
    db.commit()
    return serialize_template(_get_active_template(db, template_id))


MAX_BOM_DRAWING_SIZE = 10 * 1024 * 1024


def _load_template_bom(db: Session, template_id: int) -> MesProductTemplate:
    template = _get_active_template(db, template_id)
    return template


@router.get("/templates/{template_id}/bom")
def get_template_bom(
    template_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_view")
    template = _load_template_bom(db, template_id)
    return serialize_bom(template)


@router.post("/templates/{template_id}/bom")
def add_template_bom_line(
    template_id: int,
    data: BomLineCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_edit")
    template = _load_template_bom(db, template_id)
    try:
        validate_required_quantity(data.required_quantity)
        part = get_active_part(db, data.part_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing = (
        db.query(MesBomLine)
        .filter(
            MesBomLine.template_id == template_id,
            MesBomLine.part_id == data.part_id,
        )
        .first()
    )
    if existing:
        if existing.is_active and existing.deleted_at is None:
            raise HTTPException(status_code=400, detail="Part already in BOM")
        existing.is_active = True
        existing.deleted_at = None
        existing.required_quantity = float(data.required_quantity)
        existing.produced_quantity = float(data.produced_quantity or 0)
        existing.accepted_quantity = float(data.accepted_quantity or 0)
        existing.rejected_quantity = float(data.rejected_quantity or 0)
        existing.notes = data.notes or ""
        existing.drawing_url = data.drawing_url or None
        existing.unit = part.unit
        existing.sort_order = (
            data.sort_order if data.sort_order is not None else next_sort_order(db, template_id)
        )
        line = existing
    else:
        line = MesBomLine(
            template_id=template.id,
            part_id=part.id,
            required_quantity=float(data.required_quantity),
            produced_quantity=float(data.produced_quantity or 0),
            accepted_quantity=float(data.accepted_quantity or 0),
            rejected_quantity=float(data.rejected_quantity or 0),
            unit=part.unit,
            notes=data.notes or "",
            drawing_url=data.drawing_url or None,
            sort_order=data.sort_order
            if data.sort_order is not None
            else next_sort_order(db, template_id),
        )
        db.add(line)

    template.updated_at = datetime.utcnow()
    log_action(
        db,
        user.username,
        "create",
        "mes_bom_line",
        template_id,
        f"part {part.part_number}",
    )
    db.commit()
    db.refresh(line)
    line = find_bom_line(db, template_id, line.id) or line
    if line.part is None:
        line.part = part
    return serialize_bom_line(line)


@router.put("/templates/{template_id}/bom/reorder")
def reorder_template_bom(
    template_id: int,
    data: BomReorder,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_edit")
    _load_template_bom(db, template_id)
    if not data.lines:
        raise HTTPException(status_code=400, detail="No lines to reorder")

    line_ids = [item.id for item in data.lines]
    rows = (
        db.query(MesBomLine)
        .filter(
            MesBomLine.template_id == template_id,
            MesBomLine.id.in_(line_ids),
            MesBomLine.is_active.is_(True),
            MesBomLine.deleted_at.is_(None),
        )
        .all()
    )
    if len(rows) != len(line_ids):
        raise HTTPException(status_code=400, detail="Invalid BOM line ids")

    order_map = {item.id: item.sort_order for item in data.lines}
    for row in rows:
        row.sort_order = order_map[row.id]

    log_action(db, user.username, "reorder", "mes_bom", template_id)
    db.commit()
    return serialize_bom(_get_active_template(db, template_id))


@router.put("/templates/{template_id}/bom/{line_id}")
def update_template_bom_line(
    template_id: int,
    line_id: int,
    data: BomLineUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_edit")
    _load_template_bom(db, template_id)
    line = find_bom_line(db, template_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="BOM line not found")

    if data.required_quantity is not None:
        try:
            validate_required_quantity(data.required_quantity)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        line.required_quantity = float(data.required_quantity)
    if data.produced_quantity is not None:
        line.produced_quantity = float(data.produced_quantity)
    if data.accepted_quantity is not None:
        line.accepted_quantity = float(data.accepted_quantity)
    if data.rejected_quantity is not None:
        line.rejected_quantity = float(data.rejected_quantity)
    if data.notes is not None:
        line.notes = data.notes
    if data.drawing_url is not None:
        line.drawing_url = data.drawing_url or None
    if data.sort_order is not None:
        line.sort_order = int(data.sort_order)

    log_action(db, user.username, "update", "mes_bom_line", line_id, str(template_id))
    db.commit()
    db.refresh(line)
    return serialize_bom_line(line)


@router.delete("/templates/{template_id}/bom/{line_id}")
def delete_template_bom_line(
    template_id: int,
    line_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_edit")
    _load_template_bom(db, template_id)
    line = find_bom_line(db, template_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="BOM line not found")

    line.is_active = False
    line.deleted_at = datetime.utcnow()
    log_action(db, user.username, "delete", "mes_bom_line", line_id, str(template_id))
    db.commit()
    return {"message": "BOM line removed"}


@router.post("/templates/{template_id}/bom/{line_id}/drawing")
async def upload_bom_line_drawing(
    template_id: int,
    line_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    file: UploadFile = File(...),
):
    _require(db, user, "mes_edit")
    _load_template_bom(db, template_id)
    line = find_bom_line(db, template_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="BOM line not found")

    content = await file.read()
    if len(content) > MAX_BOM_DRAWING_SIZE:
        raise HTTPException(status_code=400, detail="Drawing too large (max 10MB)")
    try:
        saved = save_bom_drawing(content, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    line.drawing_url = saved["url"]
    log_action(db, user.username, "upload", "mes_bom_drawing", line_id, str(template_id))
    db.commit()
    db.refresh(line)
    return serialize_bom_line(line)


def _serialize_stage(stage: MesProductionStage) -> dict:
    return {
        "id": stage.id,
        "name": stage.name,
        "department": stage.department or "Admin",
        "sort_order": stage.sort_order,
        "color": stage.color,
        "is_active": bool(stage.is_active),
        "is_system": bool(stage.is_system),
        "created_at": stage.created_at,
    }


def _get_active_stage(db: Session, stage_id: int) -> MesProductionStage:
    stage = (
        db.query(MesProductionStage)
        .filter(
            MesProductionStage.id == stage_id,
            MesProductionStage.is_active.is_(True),
        )
        .first()
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    return stage


@router.get("/stages")
def list_stages(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    include_inactive: bool = Query(False),
):
    _require(db, user, "mes_view")
    query = db.query(MesProductionStage).order_by(
        MesProductionStage.sort_order, MesProductionStage.name
    )
    if not include_inactive:
        query = query.filter(MesProductionStage.is_active.is_(True))
    stages = query.all()
    return {"stages": [_serialize_stage(s) for s in stages]}


@router.post("/stages")
def create_stage(
    data: StageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_route_design(db, user)
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Stage name required")
    existing = (
        db.query(MesProductionStage)
        .filter(MesProductionStage.name == name, MesProductionStage.is_active.is_(True))
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Stage name already exists")

    stage = MesProductionStage(
        name=name,
        department=(data.department or "Admin").strip() or "Admin",
        color=data.color,
        sort_order=data.sort_order,
        is_system=False,
        is_active=True,
    )
    db.add(stage)
    log_action(db, user.username, "create", "mes_stage", details=name)
    db.commit()
    db.refresh(stage)
    return _serialize_stage(stage)


@router.put("/stages/{stage_id}")
def update_stage(
    stage_id: int,
    data: StageUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_route_design(db, user)
    stage = db.query(MesProductionStage).filter(MesProductionStage.id == stage_id).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")

    if data.name is not None:
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Stage name required")
        clash = (
            db.query(MesProductionStage)
            .filter(
                MesProductionStage.name == name,
                MesProductionStage.id != stage_id,
                MesProductionStage.is_active.is_(True),
            )
            .first()
        )
        if clash:
            raise HTTPException(status_code=400, detail="Stage name already exists")
        stage.name = name
    if data.department is not None:
        stage.department = data.department.strip() or stage.department
    if data.color is not None:
        stage.color = data.color or None
    if data.sort_order is not None:
        stage.sort_order = data.sort_order
    if data.is_active is not None:
        stage.is_active = bool(data.is_active)

    log_action(db, user.username, "update", "mes_stage", stage_id, stage.name)
    db.commit()
    db.refresh(stage)
    return _serialize_stage(stage)


@router.delete("/stages/{stage_id}")
def delete_stage(
    stage_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_route_design(db, user)
    stage = (
        db.query(MesProductionStage)
        .filter(MesProductionStage.id == stage_id, MesProductionStage.is_active.is_(True))
        .first()
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")

    in_use = (
        db.query(MesRouteStep)
        .filter(MesRouteStep.stage_id == stage_id)
        .limit(1)
        .count()
    )
    if in_use:
        raise HTTPException(status_code=400, detail="Stage is used in production routes")

    stage.is_active = False
    log_action(db, user.username, "delete", "mes_stage", stage_id, stage.name)
    db.commit()
    return {"message": "Stage deactivated"}


@router.get("/templates/{template_id}/routes")
def list_template_routes(
    template_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_view")
    template = _get_active_template(db, template_id)
    routes = active_routes(template)
    return {"routes": [serialize_route(route, template) for route in routes]}


@router.get("/templates/{template_id}/routes/{route_id}")
def get_template_route(
    template_id: int,
    route_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_view")
    template = _get_active_template(db, template_id)
    route = get_active_route(db, template_id, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return serialize_route(route, template)


@router.post("/templates/{template_id}/routes")
def create_template_route(
    template_id: int,
    data: RouteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_route_design(db, user)
    template = _get_active_template(db, template_id)
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Route name required")

    route = MesProductionRoute(
        template_id=template.id,
        name=name,
        version=max(1, int(data.version or 1)),
        is_default=False,
        is_active=True,
        created_by=user.username,
    )
    db.add(route)
    db.flush()

    if data.is_default or not active_routes(template):
        set_default_route(db, template, route)

    template.updated_at = datetime.utcnow()
    log_action(db, user.username, "create", "mes_route", route.id, name)
    db.commit()
    route = get_active_route(db, template_id, route.id)
    return serialize_route(route, _get_active_template(db, template_id))


@router.put("/templates/{template_id}/routes/{route_id}")
def update_template_route(
    template_id: int,
    route_id: int,
    data: RouteUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_route_design(db, user)
    template = _get_active_template(db, template_id)
    route = get_active_route(db, template_id, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    if data.name is not None:
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Route name required")
        route.name = name

    template.updated_at = datetime.utcnow()
    log_action(db, user.username, "update", "mes_route", route_id, route.name)
    db.commit()
    return serialize_route(route, template)


@router.delete("/templates/{template_id}/routes/{route_id}")
def delete_template_route(
    template_id: int,
    route_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_route_design(db, user)
    template = _get_active_template(db, template_id)
    route = get_active_route(db, template_id, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    route.is_active = False
    route.deleted_at = datetime.utcnow()
    route.is_default = False
    if template.default_route_id == route_id:
        template.default_route_id = None
        remaining = [
            r for r in active_routes(template) if r.id != route_id
        ]
        if remaining:
            set_default_route(db, template, remaining[0])

    template.updated_at = datetime.utcnow()
    log_action(db, user.username, "delete", "mes_route", route_id, route.name)
    db.commit()
    return {"message": "Route deactivated"}


@router.post("/templates/{template_id}/routes/{route_id}/set-default")
def set_template_default_route(
    template_id: int,
    route_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_route_design(db, user)
    template = _get_active_template(db, template_id)
    route = get_active_route(db, template_id, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    set_default_route(db, template, route)
    template.updated_at = datetime.utcnow()
    log_action(db, user.username, "set_default", "mes_route", route_id, route.name)
    db.commit()
    return serialize_route(route, template)


@router.post("/templates/{template_id}/routes/{route_id}/new-version")
def create_route_new_version(
    template_id: int,
    route_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_route_design(db, user)
    template = _get_active_template(db, template_id)
    source = get_active_route(db, template_id, route_id)
    if not source:
        raise HTTPException(status_code=404, detail="Route not found")

    max_version = (
        db.query(MesProductionRoute.version)
        .filter(
            MesProductionRoute.template_id == template_id,
            MesProductionRoute.name == source.name,
            MesProductionRoute.deleted_at.is_(None),
        )
        .order_by(MesProductionRoute.version.desc())
        .first()
    )
    next_version = (max_version[0] if max_version else source.version) + 1

    route = MesProductionRoute(
        template_id=template.id,
        name=source.name,
        version=next_version,
        is_default=False,
        is_active=True,
        created_by=user.username,
    )
    db.add(route)
    db.flush()
    copy_route_steps(source, route)

    template.updated_at = datetime.utcnow()
    log_action(
        db,
        user.username,
        "version",
        "mes_route",
        route.id,
        f"v{next_version} from {route_id}",
    )
    db.commit()
    route = get_active_route(db, template_id, route.id)
    return serialize_route(route, _get_active_template(db, template_id))


@router.post("/templates/{template_id}/routes/{route_id}/steps")
def add_route_step(
    template_id: int,
    route_id: int,
    data: RouteStepCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_route_design(db, user)
    template = _get_active_template(db, template_id)
    route = get_active_route(db, template_id, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    stage = _get_active_stage(db, data.stage_id)
    step = MesRouteStep(
        route_id=route.id,
        stage_id=stage.id,
        step_order=data.step_order
        if data.step_order is not None
        else next_step_order(route),
        department=(data.department or stage.department or "Admin").strip() or None,
        responsible_role=(data.responsible_role or "").strip() or None,
        estimated_minutes=data.estimated_minutes,
        required_parts_count=max(0, int(data.required_parts_count or 0)),
        completed_parts_count=max(0, int(data.completed_parts_count or 0)),
        instructions=data.instructions or "",
        is_required=bool(data.is_required),
    )
    db.add(step)
    template.updated_at = datetime.utcnow()
    log_action(db, user.username, "create", "mes_route_step", route_id, stage.name)
    db.commit()
    db.refresh(step)
    step.stage = stage
    return serialize_route_step(step)


@router.put("/templates/{template_id}/routes/{route_id}/steps/reorder")
def reorder_route_steps(
    template_id: int,
    route_id: int,
    data: RouteStepReorder,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_route_design(db, user)
    template = _get_active_template(db, template_id)
    route = get_active_route(db, template_id, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    if not data.steps:
        raise HTTPException(status_code=400, detail="No steps to reorder")

    step_ids = [item.id for item in data.steps]
    rows = (
        db.query(MesRouteStep)
        .filter(MesRouteStep.route_id == route_id, MesRouteStep.id.in_(step_ids))
        .all()
    )
    if len(rows) != len(step_ids):
        raise HTTPException(status_code=400, detail="Invalid step ids")

    order_map = {item.id: item.step_order for item in data.steps}
    for row in rows:
        row.step_order = -row.id
    db.flush()
    for row in rows:
        row.step_order = order_map[row.id]

    template.updated_at = datetime.utcnow()
    log_action(db, user.username, "reorder", "mes_route_steps", route_id)
    db.commit()
    route = get_active_route(db, template_id, route_id)
    return serialize_route(route, template)


@router.put("/templates/{template_id}/routes/{route_id}/steps/{step_id}")
def update_route_step(
    template_id: int,
    route_id: int,
    step_id: int,
    data: RouteStepUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_route_design(db, user)
    template = _get_active_template(db, template_id)
    route = get_active_route(db, template_id, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    step = next((s for s in active_route_steps(route) if s.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="Route step not found")

    if data.stage_id is not None:
        stage = _get_active_stage(db, data.stage_id)
        step.stage_id = stage.id
        step.stage = stage
    if data.department is not None:
        step.department = data.department.strip() or None
    if data.responsible_role is not None:
        step.responsible_role = data.responsible_role.strip() or None
    if data.estimated_minutes is not None:
        step.estimated_minutes = data.estimated_minutes
    if data.required_parts_count is not None:
        step.required_parts_count = max(0, int(data.required_parts_count))
    if data.completed_parts_count is not None:
        step.completed_parts_count = max(0, int(data.completed_parts_count))
    if data.instructions is not None:
        step.instructions = data.instructions
    if data.is_required is not None:
        step.is_required = bool(data.is_required)

    template.updated_at = datetime.utcnow()
    log_action(db, user.username, "update", "mes_route_step", step_id, str(route_id))
    db.commit()
    db.refresh(step)
    return serialize_route_step(step)


@router.delete("/templates/{template_id}/routes/{route_id}/steps/{step_id}")
def delete_route_step(
    template_id: int,
    route_id: int,
    step_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_route_design(db, user)
    template = _get_active_template(db, template_id)
    route = get_active_route(db, template_id, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    step = db.query(MesRouteStep).filter(
        MesRouteStep.id == step_id, MesRouteStep.route_id == route_id
    ).first()
    if not step:
        raise HTTPException(status_code=404, detail="Route step not found")

    db.delete(step)
    template.updated_at = datetime.utcnow()
    log_action(db, user.username, "delete", "mes_route_step", step_id, str(route_id))
    db.commit()
    return {"message": "Route step removed"}


def _get_active_drawing(
    db: Session, template_id: int, drawing_id: int
) -> MesProductDrawing | None:
    return (
        db.query(MesProductDrawing)
        .filter(
            MesProductDrawing.id == drawing_id,
            MesProductDrawing.template_id == template_id,
            MesProductDrawing.is_active.is_(True),
            MesProductDrawing.deleted_at.is_(None),
        )
        .first()
    )


@router.get("/templates/{template_id}/drawings")
def list_template_drawings(
    template_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_view")
    template = _get_active_template(db, template_id)
    return serialize_drawings(template)


@router.post("/templates/{template_id}/drawings")
async def upload_template_drawing(
    template_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    file: UploadFile = File(...),
    title: str = Query(""),
    revision: str = Query("A"),
    is_primary: bool = Query(False),
):
    _require_drawings_upload(db, user)
    template = _get_active_template(db, template_id)

    content = await file.read()
    try:
        saved = save_drawing_file(content, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    drawing_title = (title or "").strip() or (file.filename or "Drawing")
    rev = (revision or "A").strip() or "A"

    if is_primary or not active_drawings(template):
        clear_primary_drawings(template)
        is_primary = True

    drawing = MesProductDrawing(
        template_id=template.id,
        title=drawing_title,
        url=saved["url"],
        filename=saved["filename"],
        original_filename=saved["original_filename"],
        content_type=saved["content_type"],
        file_size=saved["file_size"],
        revision=rev,
        is_primary=bool(is_primary),
        uploaded_by=user.username,
    )
    db.add(drawing)
    template.updated_at = datetime.utcnow()
    log_action(db, user.username, "upload", "mes_drawing", template_id, drawing_title)
    db.commit()
    db.refresh(drawing)
    return serialize_drawing(drawing)


@router.put("/templates/{template_id}/drawings/{drawing_id}")
def update_template_drawing(
    template_id: int,
    drawing_id: int,
    data: DrawingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_drawings_upload(db, user)
    template = _get_active_template(db, template_id)
    drawing = _get_active_drawing(db, template_id, drawing_id)
    if not drawing:
        raise HTTPException(status_code=404, detail="Drawing not found")

    if data.title is not None:
        title = data.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Drawing title required")
        drawing.title = title
    if data.revision is not None:
        drawing.revision = data.revision.strip() or drawing.revision
    if data.is_primary is not None:
        if data.is_primary:
            clear_primary_drawings(template)
            drawing.is_primary = True
        else:
            drawing.is_primary = False

    template.updated_at = datetime.utcnow()
    log_action(db, user.username, "update", "mes_drawing", drawing_id, drawing.title)
    db.commit()
    db.refresh(drawing)
    return serialize_drawing(drawing)


@router.post("/templates/{template_id}/drawings/{drawing_id}/set-primary")
def set_primary_drawing(
    template_id: int,
    drawing_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_drawings_upload(db, user)
    template = _get_active_template(db, template_id)
    drawing = _get_active_drawing(db, template_id, drawing_id)
    if not drawing:
        raise HTTPException(status_code=404, detail="Drawing not found")

    clear_primary_drawings(template)
    drawing.is_primary = True
    template.updated_at = datetime.utcnow()
    log_action(db, user.username, "set_primary", "mes_drawing", drawing_id, drawing.title)
    db.commit()
    db.refresh(drawing)
    return serialize_drawing(drawing)


@router.delete("/templates/{template_id}/drawings/{drawing_id}")
def delete_template_drawing(
    template_id: int,
    drawing_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "mes_delete")
    template = _get_active_template(db, template_id)
    drawing = _get_active_drawing(db, template_id, drawing_id)
    if not drawing:
        raise HTTPException(status_code=404, detail="Drawing not found")

    was_primary = drawing.is_primary
    drawing.is_active = False
    drawing.deleted_at = datetime.utcnow()
    drawing.is_primary = False

    if was_primary:
        remaining = [d for d in active_drawings(template) if d.id != drawing_id]
        if remaining:
            remaining[0].is_primary = True

    template.updated_at = datetime.utcnow()
    log_action(db, user.username, "delete", "mes_drawing", drawing_id, drawing.title)
    db.commit()
    return {"message": "Drawing removed"}
