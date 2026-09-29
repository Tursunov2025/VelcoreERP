"""Concurrent detail-stock reservation and issue test.

Set TEST_POSTGRES_DATABASE_URL to run this against the production database
engine family.  Without it the test uses SQLite and verifies the conditional
write fallback; SQLite cannot validate PostgreSQL's FOR UPDATE row locks.
"""
from __future__ import annotations

import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

postgres_url = os.getenv("TEST_POSTGRES_DATABASE_URL")
test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
if postgres_url:
    os.environ["DATABASE_URL"] = postgres_url
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db.replace(chr(92), '/')}"
test_root = Path(tempfile.mkdtemp(prefix="velcore-stock-race-"))
os.environ["DATA_ROOT"] = str(test_root)
os.environ["DB_PATH"] = test_db
os.environ["UPLOAD_PATH"] = str(test_root / "uploads")
os.environ["BACKUP_PATH"] = str(test_root / "backups")
os.environ["LOG_PATH"] = str(test_root / "logs")

backend = Path(__file__).resolve().parent
sys.path.insert(0, str(backend))

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from models import MesProductPart, WarehouseStock, WarehouseTransaction  # noqa: E402
from services.warehouse_stock import change_stock  # noqa: E402


def _attempt(stock_id: int, operation: str, start: Barrier) -> str:
    db = SessionLocal()  # Deliberately independent DB session per operator.
    try:
        start.wait(timeout=10)
        change_stock(db, stock_id, 5, operation, f"race-{operation.lower()}")
        db.commit()
        return "success"
    except ValueError:
        db.rollback()
        return "rejected"
    finally:
        db.close()


def _race(db, stock_id: int, operation: str) -> None:
    # Both workers operate on the same stock id at the same time, but never
    # share a SQLAlchemy session or transaction.
    start = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _attempt(stock_id, operation, start), range(2)))
    db.expire_all()
    stock = db.query(WarehouseStock).filter_by(id=stock_id).one()
    transactions = db.query(WarehouseTransaction).filter_by(stock_id=stock_id, operation=operation).all()
    successful_quantity = sum(float(tx.quantity) for tx in transactions)
    assert stock.quantity >= 0 and stock.reserved_quantity >= 0
    assert stock.reserved_quantity <= stock.quantity
    assert successful_quantity <= 5
    assert successful_quantity == results.count("success") * 5
    assert len(transactions) == results.count("success")


def main() -> None:
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        run_migrations()
    db = SessionLocal()
    try:
        part = MesProductPart(part_number="RACE-D-125", name="Race detail", created_by="test")
        db.add(part)
        db.flush()

        reserve_stock = WarehouseStock(detail_id=part.id, detail_code=part.part_number, detail_name=part.name, quantity=5, unit="dona", status="READY")
        out_stock = WarehouseStock(detail_id=part.id, detail_code=part.part_number, detail_name=part.name, quantity=5, unit="dona", status="READY")
        db.add_all([reserve_stock, out_stock])
        db.commit()

        _race(db, reserve_stock.id, "RESERVE")
        _race(db, out_stock.id, "OUT")
        print(f"test_svarshik_stock_concurrency: OK ({engine.dialect.name})")
        if engine.dialect.name != "postgresql":
            print("PostgreSQL FOR UPDATE integration: SKIPPED (set TEST_POSTGRES_DATABASE_URL to validate production row-lock semantics)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
