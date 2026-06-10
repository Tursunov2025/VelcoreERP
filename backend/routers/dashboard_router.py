"""Phase 11B — Dashboard KPI cards (single aggregated endpoint)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import (
    Document,
    ExportShipment,
    Material,
    MesFinishedGoodsInventory,
    MesProductionJob,
    Order,
    ShipmentItem,
    User,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis")
def dashboard_kpis(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    orders_count = db.query(Order).filter(Order.deleted_at.is_(None)).count()
    customers_count = (
        db.query(func.count(distinct(Order.client)))
        .filter(Order.deleted_at.is_(None))
        .scalar()
        or 0
    )
    finished_products = (
        db.query(func.coalesce(func.sum(MesFinishedGoodsInventory.quantity), 0))
        .filter(MesFinishedGoodsInventory.status == "in_stock")
        .scalar()
        or 0
    )
    shipped_orders = (
        db.query(func.count(distinct(ShipmentItem.order_id)))
        .filter(ShipmentItem.order_id.isnot(None))
        .scalar()
        or 0
    )
    return {
        "orders": orders_count,
        "production_jobs": db.query(MesProductionJob).count(),
        "finished_products": float(finished_products),
        "shipped_orders": shipped_orders,
        "customers": customers_count,
        "materials": db.query(Material).filter(Material.is_active.is_(True)).count(),
        "llp_documents": db.query(Document).count(),
        "export_shipments": db.query(ExportShipment).count(),
    }
