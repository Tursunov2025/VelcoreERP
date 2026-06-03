"""Production backup restore smoke test (ephemeral DB under temp DATA_ROOT)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="azmus_prod_test_"))
os.environ["DATA_ROOT"] = str(TMP / "Data")
os.environ["DB_PATH"] = str(TMP / "Data" / "database" / "azmus.db")
os.environ["UPLOAD_PATH"] = str(TMP / "Data" / "uploads")
os.environ["BACKUP_PATH"] = str(TMP / "Data" / "backups")
os.environ["LOG_PATH"] = str(TMP / "Data" / "logs")
os.environ["MIGRATION_BACKUP_PATH"] = str(TMP / "Data" / "migrations")
os.environ["DATABASE_URL"] = f"sqlite:///{os.environ['DB_PATH'].replace(chr(92), '/')}"
os.environ.setdefault("JWT_SECRET_KEY", "test-production-backup")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from services.auto_backup import restore_database_from_backup, run_daily_backup  # noqa: E402
from services.seed import seed_defaults  # noqa: E402


def test_backup_and_restore():
    Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    seed_defaults(db)
    db.close()

    result = run_daily_backup()
    assert result["status"] == "ok"
    backup_file = Path(result["database_backup"])
    assert backup_file.is_file()

    restore_database_from_backup(backup_file)
    print("Production backup/restore: PASSED")
    print("Temp data:", TMP)


if __name__ == "__main__":
    test_backup_and_restore()
