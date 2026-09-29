"""Dry-run/apply QC predecessor reconciliation on an explicit disposable SQLite DB."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--database-url", required=True)
parser.add_argument("--job-id", type=int)
parser.add_argument("--apply", action="store_true")
parser.add_argument("--actor", default="qc-reconciliation")
parser.add_argument("--confirm-production-path")
args = parser.parse_args()

if not args.database_url.startswith("sqlite:///"):
    raise SystemExit("Only an explicit disposable SQLite database is supported")
path = Path(args.database_url.removeprefix("sqlite:///")).resolve()
normalized = path.as_posix().lower()
disposable = "/temp/azmus-checkpoint-e-" in normalized
if args.apply and not disposable:
    confirmed = Path(args.confirm_production_path).resolve() if args.confirm_production_path else None
    if args.job_id is None or confirmed != path:
        raise SystemExit("Production apply requires --job-id and --confirm-production-path matching the explicit database")
os.environ["DATABASE_URL"] = args.database_url
os.environ["DB_PATH"] = str(path)
if disposable:
    os.environ["DATA_ROOT"] = str(path.parent / "runtime")
    os.environ["DATABASE_GUARD"] = "false"
    os.environ["ENVIRONMENT"] = "test"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import SessionLocal  # noqa: E402
from services.qc_predecessor_reconciliation import reconcile_qc_predecessors  # noqa: E402

db = SessionLocal()
try:
    result = reconcile_qc_predecessors(db, job_id=args.job_id, dry_run=not args.apply, actor=args.actor)
    if args.apply:
        db.commit()
    else:
        db.rollback()
    print(json.dumps(result, ensure_ascii=False, indent=2))
except Exception:
    db.rollback()
    raise
finally:
    db.close()
