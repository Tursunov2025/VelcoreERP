"""Seed MES master data (production stages)."""

from sqlalchemy.orm import Session

from models import MesProductionStage
from services.mes_qc_terminal import seed_qc_rejection_reasons
from services.mes_warehouse_terminal import seed_warehouse_locations
from services.settings_runtime import get_mes_default_stages


def seed_mes_defaults(db: Session) -> None:
    stages = get_mes_default_stages(db)
    for order, (name, department) in enumerate(stages):
        existing = (
            db.query(MesProductionStage).filter(MesProductionStage.name == name).first()
        )
        if not existing:
            db.add(
                MesProductionStage(
                    name=name,
                    department=department,
                    sort_order=order,
                    is_system=True,
                    is_active=True,
                )
            )
        else:
            existing.department = department
            existing.sort_order = order
            existing.is_active = True
    db.commit()
    seed_qc_rejection_reasons(db)
    seed_warehouse_locations(db)
