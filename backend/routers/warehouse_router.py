from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth.deps import get_current_user, require_admin
from database import get_db
from models import Material, MesJobBomLine, Order, StockMovement, User, WarehouseItem, WarehouseStock, WarehouseTransaction
from services.warehouse_stock import add_surplus, change_stock
from services.mes_jobs import load_job
from schemas import MaterialCreate, MaterialResponse, StockMovementCreate, StockMovementResponse, WarehouseItemResponse
from services.notifications import notify_event
from services.permissions import require_project_job_permission, user_has_permission
from services.telegram import format_warehouse_movement_alert

router = APIRouter(prefix="/warehouse", tags=["warehouse"])

def _can_write(user): return user.role == "admin" or user.department in ("Ombor", "Admin")


def _can_read_reusable_stock(db: Session, user: User) -> bool:
    return (
        _can_write(user)
        or user.department == "Svarka"
        or user_has_permission(db, user, "mes_terminal_lazer")
    )

@router.get("/stock")
def reusable_stock(q: str = "", status: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_read_reusable_stock(db, user):
        raise HTTPException(403, "Warehouse access required")
    query = db.query(WarehouseStock)
    if status: query = query.filter(WarehouseStock.status == status)
    if q: query = query.filter((WarehouseStock.detail_code.ilike(f"%{q}%")) | (WarehouseStock.detail_name.ilike(f"%{q}%")))
    return [{"id": s.id, "detail_id": s.detail_id, "detail_code": s.detail_code, "detail_name": s.detail_name, "dimensions": s.dimensions, "material": s.material, "thickness": s.thickness, "quantity": s.quantity, "reserved_quantity": s.reserved_quantity, "available_quantity": s.quantity-s.reserved_quantity, "unit": s.unit, "status": "TAYYOR" if s.quantity-s.reserved_quantity > 0 else "QOLDIQ YO'Q", "created_at": s.created_at, "updated_at": s.updated_at} for s in query.order_by(WarehouseStock.created_at.desc()).all()]

@router.get("/stock/{detail_id}")
def reusable_stock_detail(detail_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_read_reusable_stock(db, user): raise HTTPException(403, "Warehouse access required")
    return reusable_stock(q="", db=db, user=user) if detail_id == 0 else [{"id": s.id, "detail_id": s.detail_id, "detail_code": s.detail_code, "detail_name": s.detail_name, "quantity": s.quantity, "reserved_quantity": s.reserved_quantity, "available_quantity": s.quantity-s.reserved_quantity, "status": "TAYYOR" if s.quantity-s.reserved_quantity > 0 else "QOLDIQ YO'Q"} for s in db.query(WarehouseStock).filter(WarehouseStock.detail_id == detail_id).all()]

@router.get("/transactions")
def reusable_transactions(operation: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    is_lazer_reader = user_has_permission(db, user, "mes_terminal_lazer")
    if not _can_write(user) and not is_lazer_reader:
        raise HTTPException(403, "Warehouse access required")
    normalized_operation = operation.strip().upper()
    if not _can_write(user) and normalized_operation != "IN":
        raise HTTPException(403, "Lazer operators may only view IN transactions")
    query = db.query(WarehouseTransaction)
    if normalized_operation:
        query = query.filter(WarehouseTransaction.operation == normalized_operation)
    return query.order_by(WarehouseTransaction.created_at.desc()).limit(200).all()

@router.post("/stock/in")
def reusable_stock_in(job_id: int, bom_line_id: int, quantity: float, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = load_job(db, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.project_id:
        if not user_has_permission(db, user, "mes_terminal_lazer"):
            raise HTTPException(403, "Permission required: mes_terminal_lazer")
        require_project_job_permission(db, user, job, "production_projects_execute")
    elif user.role != "admin" and user.department not in ("Svarka", "Ombor", "Admin"):
        raise HTTPException(403, "Warehouse write access required")
    line = (
        db.query(MesJobBomLine)
        .with_for_update()
        .filter(MesJobBomLine.id == bom_line_id, MesJobBomLine.job_id == job_id)
        .first()
    )
    if not line: raise HTTPException(404, "BOM line not found")
    surplus = float(line.completed_quantity or 0) - float(line.allocated_quantity or 0) - float(line.surplus_stocked_quantity or 0)
    if quantity <= 0 or quantity > surplus: raise HTTPException(400, "Invalid surplus quantity")
    try:
        stock = add_surplus(db, line, job_id, quantity, user.username)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    return {"id": stock.id, "quantity": stock.quantity, "status": "TAYYOR"}

@router.post("/stock/out")
def reusable_stock_out(stock_id: int, quantity: float, reason: str = "", job_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_write(user): raise HTTPException(403, "Warehouse write access required")
    try: stock = change_stock(db, stock_id, quantity, "OUT", user.username, job_id, reason); db.commit()
    except ValueError as exc: db.rollback(); raise HTTPException(400, str(exc))
    return {"id": stock.id, "quantity": stock.quantity, "available_quantity": stock.quantity-stock.reserved_quantity}

@router.post("/stock/reserve")
def reusable_stock_reserve(stock_id: int, quantity: float, job_id: int | None = None, reason: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_write(user): raise HTTPException(403, "Warehouse write access required")
    try: stock = change_stock(db, stock_id, quantity, "RESERVE", user.username, job_id, reason); db.commit()
    except ValueError as exc: db.rollback(); raise HTTPException(400, str(exc))
    return {"id": stock.id, "reserved_quantity": stock.reserved_quantity}

@router.post("/stock/release")
def reusable_stock_release(stock_id: int, quantity: float, job_id: int | None = None, reason: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_write(user): raise HTTPException(403, "Warehouse write access required")
    try: stock = change_stock(db, stock_id, quantity, "RELEASE", user.username, job_id, reason); db.commit()
    except ValueError as exc: db.rollback(); raise HTTPException(400, str(exc))
    return {"id": stock.id, "reserved_quantity": stock.reserved_quantity}

@router.post("/stock/adjustment")
def reusable_stock_adjustment(stock_id: int, quantity: float, reason: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_write(user): raise HTTPException(403, "Warehouse write access required")
    try: stock = change_stock(db, stock_id, quantity, "ADJUSTMENT", user.username, None, reason); db.commit()
    except ValueError as exc: db.rollback(); raise HTTPException(400, str(exc))
    return {"id": stock.id, "quantity": stock.quantity}


def _material_response(material: Material) -> MaterialResponse:
    return MaterialResponse(
        id=material.id,
        name=material.name,
        unit=material.unit,
        quantity=material.quantity,
        min_quantity=material.min_quantity,
        low_stock=material.quantity <= material.min_quantity,
    )


@router.get("/ready", response_model=list[WarehouseItemResponse])
def ready_products(
    search: str = Query("", alias="q"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin" and user.department not in ("Ombor", "Admin"):
        raise HTTPException(status_code=403, detail="Ombor access required")

    query = db.query(WarehouseItem).order_by(WarehouseItem.stored_at.desc())
    items = query.all()

    if search.strip():
        q = search.lower()
        items = [
            i
            for i in items
            if q in (i.client or "").lower()
            or q in (i.destination or "").lower()
            or q in str(i.order_id)
        ]
    return items


@router.get("/materials", response_model=list[MaterialResponse])
def list_materials(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    materials = db.query(Material).order_by(Material.name).all()
    return [_material_response(m) for m in materials]


@router.post("/materials", response_model=MaterialResponse)
def create_material(
    data: MaterialCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if db.query(Material).filter(Material.name == data.name).first():
        raise HTTPException(status_code=400, detail="Material already exists")
    material = Material(**data.model_dump())
    db.add(material)
    db.commit()
    db.refresh(material)
    return _material_response(material)


@router.get("/alerts", response_model=list[MaterialResponse])
def low_stock_alerts(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    materials = db.query(Material).all()
    return [_material_response(m) for m in materials if m.quantity <= m.min_quantity]


@router.post("/movements", response_model=StockMovementResponse)
async def stock_movement(
    data: StockMovementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    material = db.query(Material).filter(Material.id == data.material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    if data.movement_type == "out" and material.quantity < data.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    if data.movement_type == "in":
        material.quantity += data.quantity
    else:
        material.quantity -= data.quantity

    movement = StockMovement(
        material_id=data.material_id,
        movement_type=data.movement_type,
        quantity=data.quantity,
        note=data.note,
        created_by=user.username,
    )
    db.add(movement)
    db.commit()
    db.refresh(movement)
    await notify_event(
        db,
        "warehouse_events",
        format_warehouse_movement_alert(material, movement, user.username),
    )
    return movement


@router.get("/history", response_model=list[StockMovementResponse])
def movement_history(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return (
        db.query(StockMovement)
        .order_by(StockMovement.created_at.desc())
        .limit(100)
        .all()
    )
