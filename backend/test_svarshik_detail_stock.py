"""Focused reusable SVARKA detail-stock service tests."""
from __future__ import annotations
import os, sys, tempfile
from pathlib import Path

TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.replace(chr(92), '/') }"
TEST_ROOT = Path(tempfile.mkdtemp(prefix="velcore-stock-"))
os.environ["DATA_ROOT"] = str(TEST_ROOT)
os.environ["DB_PATH"] = TEST_DB
os.environ["UPLOAD_PATH"] = str(TEST_ROOT / "uploads")
os.environ["BACKUP_PATH"] = str(TEST_ROOT / "backups")
os.environ["LOG_PATH"] = str(TEST_ROOT / "logs")
BACKEND = Path(__file__).resolve().parent; sys.path.insert(0, str(BACKEND))
from database import Base, SessionLocal, engine, run_migrations  # noqa
from models import WarehouseStock, WarehouseTransaction, MesProductPart  # noqa
from services.warehouse_stock import change_stock  # noqa

def main():
    Base.metadata.create_all(bind=engine); run_migrations(); db = SessionLocal()
    part = MesProductPart(part_number="D-125", name="Test", created_by="test")
    db.add(part); db.flush()
    stock = WarehouseStock(detail_id=part.id, detail_code="D-125", detail_name="Test", quantity=5, unit="dona", status="READY")
    db.add(stock); db.commit()
    change_stock(db, stock.id, 2, "RESERVE", "operator"); db.commit()
    assert stock.reserved_quantity == 2 and stock.quantity == 5
    try: change_stock(db, stock.id, 4, "OUT", "operator")
    except ValueError: db.rollback()
    else: raise AssertionError("negative/over-consumption was allowed")
    change_stock(db, stock.id, 2, "RELEASE", "operator"); db.commit()
    change_stock(db, stock.id, 5, "OUT", "operator"); db.commit()
    assert stock.quantity == 0 and stock.reserved_quantity == 0
    assert {x.operation for x in db.query(WarehouseTransaction).all()} >= {"RESERVE", "RELEASE", "OUT"}
    db.close()
    print("test_svarshik_detail_stock: OK")
if __name__ == "__main__": main()
