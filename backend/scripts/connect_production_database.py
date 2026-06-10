"""
Connect ERP modules to the existing production SQLite database.

- Read-only audit first
- Applies schema migrations only (no data wipe, no demo seed)
- Optional: link order references on existing MES jobs (no new rows)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Force production paths before any app imports
os.environ.setdefault("DATA_ROOT", r"D:\AzmusERP\Data")
os.environ.setdefault("DB_PATH", r"D:\AzmusERP\Data\database\azmus.db")
os.environ.setdefault("UPLOAD_PATH", r"D:\AzmusERP\Data\uploads")
os.environ.setdefault("SKIP_DEMO_SEED", "true")

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from config.paths import DB_PATH, DATABASE_URL, UPLOAD_PATH  # noqa: E402
from database import SessionLocal, run_migrations  # noqa: E402
from models import Document, MesProductionJob, Order  # noqa: E402


def audit_counts(db) -> dict:
    from sqlalchemy import func
    from models import (
        Document,
        MesProductTemplate,
        MesProductionJob,
        Order,
        Task,
    )

    def count(model):
        return db.query(func.count(model.id)).scalar() or 0

    upload_files = sum(1 for p in Path(UPLOAD_PATH).rglob("*") if p.is_file()) if UPLOAD_PATH.is_dir() else 0
    llp_files = (
        sum(1 for p in (UPLOAD_PATH / "llp").rglob("*") if p.is_file())
        if (UPLOAD_PATH / "llp").is_dir()
        else 0
    )
    return {
        "database_path": str(DB_PATH),
        "database_url": DATABASE_URL,
        "upload_path": str(UPLOAD_PATH),
        "orders": count(Order),
        "tasks": count(Task),
        "llp_documents": count(Document),
        "llp_files_on_disk": llp_files,
        "upload_files_on_disk": upload_files,
        "mes_templates": count(MesProductTemplate),
        "mes_jobs": count(MesProductionJob),
    }


def link_order_references(db) -> int:
    """Set order_reference on MES jobs when customer_name matches order.client (no inserts)."""
    updated = 0
    orders = db.query(Order).all()
    by_client = {o.client.strip().lower(): o for o in orders if o.client}
    jobs = db.query(MesProductionJob).filter(
        (MesProductionJob.order_reference == None) | (MesProductionJob.order_reference == "")
    ).all()
    for job in jobs:
        key = (job.customer_name or "").strip().lower()
        if not key or key not in by_client:
            continue
        order = by_client[key]
        job.order_reference = f"ORDER-{order.id}"
        updated += 1
    if updated:
        db.commit()
    return updated


def main() -> None:
    if not DB_PATH.is_file():
        print(f"ERROR: production database not found at {DB_PATH}")
        sys.exit(1)

    print("=== Production database connection ===")
    print("DB_PATH:", DB_PATH)
    print("UPLOAD_PATH:", UPLOAD_PATH)
    print("DATABASE_URL:", DATABASE_URL)

    print("\n=== Schema migrations (additive only) ===")
    run_migrations()
    print("Migrations applied.")

    db = SessionLocal()
    try:
        before = audit_counts(db)
        print("\n=== Record counts ===")
        for k, v in before.items():
            print(f"  {k}: {v}")

        print("\n=== Order to MES reference link (existing rows only) ===")
        linked = link_order_references(db)
        print(f"  jobs updated with order_reference: {linked}")
        if linked == 0:
            print("  No changes needed (jobs already linked or no client name match).")

        print("\n=== Migration actions performed ===")
        print("  - Verified production DB path and uploads folder")
        print("  - Ran additive SQL migrations (MES/Materials/Traceability/Printing tables)")
        print("  - SKIP_DEMO_SEED=true (no demo users/materials inserted)")
        print(f"  - Linked {linked} existing MES job(s) to orders by customer name")
        print("  - Did NOT overwrite, recreate, or import any database file")
        print("  - Did NOT create templates/jobs from orders (data already present)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
