from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.deps import get_current_user, require_admin
from database import get_db
from models import Material, StockMovement, User
from schemas import (
    MaterialCreate,
    MaterialResponse,
    StockMovementCreate,
    StockMovementResponse,
)

router = APIRouter(prefix="/warehouse", tags=["warehouse"])


def _material_response(material: Material) -> MaterialResponse:
    return MaterialResponse(
        id=material.id,
        name=material.name,
        unit=material.unit,
        quantity=material.quantity,
        min_quantity=material.min_quantity,
        low_stock=material.quantity <= material.min_quantity,
    )


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
def stock_movement(
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
