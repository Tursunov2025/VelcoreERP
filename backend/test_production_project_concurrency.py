"""Two-session project release race over the same reusable detail stock."""

from __future__ import annotations

import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

POSTGRES_URL = os.getenv("TEST_POSTGRES_DATABASE_URL")
DB_FILE = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
ROOT = Path(tempfile.mkdtemp(prefix="velcore-project-race-"))
os.environ["DATABASE_URL"] = POSTGRES_URL or f"sqlite:///{DB_FILE.replace(chr(92), '/')}"
os.environ["DB_PATH"] = DB_FILE
os.environ["DATA_ROOT"] = str(ROOT)
os.environ["DATABASE_GUARD"] = "false"
os.environ["ENVIRONMENT"] = "test"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy.exc import OperationalError  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from models import (MesBomLine, MesProductionRoute, MesProductionStage, MesProductPart,
                    MesProductTemplate, MesRouteStep, ProductionProject,
                    ProductionProjectLine, ProjectStockAllocation, WarehouseStock)  # noqa: E402
from services.production_projects import ProjectError, release_project  # noqa: E402


def attempt(project_id: int, version: int, key: str, barrier: Barrier) -> str:
    db = SessionLocal()
    try:
        barrier.wait(timeout=10)
        release_project(db, project_id, version, key, key)
        db.commit()
        return "success"
    except (ProjectError, OperationalError):
        db.rollback()
        return "rejected"
    finally:
        db.close()


def main():
    Base.metadata.create_all(engine); run_migrations(); db = SessionLocal()
    stage = MesProductionStage(name="RACE-LAZER", department="Kesish")
    part = MesProductPart(part_number="PROJECT-RACE", name="Race detail", created_by="test")
    product = MesProductTemplate(code="RACE-PRODUCT", name="Race product", created_by="test")
    db.add_all([stage, part, product]); db.flush()
    route = MesProductionRoute(template_id=product.id, name="Race route", is_default=True, created_by="test")
    db.add(route); db.flush(); product.default_route_id = route.id
    db.add(MesRouteStep(route_id=route.id, stage_id=stage.id, step_order=1))
    db.add(MesBomLine(template_id=product.id, part_id=part.id, required_quantity=5, unit="dona"))
    stock = WarehouseStock(detail_id=part.id, detail_code=part.part_number, detail_name=part.name, quantity=5, reserved_quantity=0, status="READY")
    db.add(stock)
    projects = []
    for index in (1, 2):
        project = ProductionProject(project_code=f"RACE-{index}", project_name=f"Race {index}", customer_name_snapshot="Race", created_by="test", status="planned")
        db.add(project); db.flush(); db.add(ProductionProjectLine(project_id=project.id, product_id=product.id, quantity=1)); projects.append((project.id, project.version))
    db.commit(); stock_id = stock.id; db.close()

    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, project_id, version, f"project-race-key-{project_id}", barrier) for project_id, version in projects]
        results = [future.result() for future in futures]
    db = SessionLocal(); stock = db.query(WarehouseStock).filter_by(id=stock_id).one(); allocations = db.query(ProjectStockAllocation).all()
    allocated = sum(float(row.reserved_quantity) for row in allocations)
    assert stock.quantity >= 0 and 0 <= stock.reserved_quantity <= stock.quantity
    assert allocated <= 5 and stock.reserved_quantity == allocated
    assert results.count("success") == 2 and len(allocations) == 1, (results, len(allocations), allocated, stock.reserved_quantity)
    print(f"test_production_project_concurrency: OK ({engine.dialect.name}; results={results}; reserved={allocated})")
    if engine.dialect.name != "postgresql":
        print("PostgreSQL project FOR UPDATE integration: SKIPPED (set TEST_POSTGRES_DATABASE_URL for the dedicated PostgreSQL gate)")
    db.close()


if __name__ == "__main__":
    main()
