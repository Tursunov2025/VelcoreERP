"""Automatic daily SQLite (+ optional uploads) backups with retention."""

from __future__ import annotations

import logging
import os
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from config.paths import BACKUP_PATH, DB_PATH, UPLOAD_PATH, ensure_data_directories
from database import DATABASE_URL

logger = logging.getLogger("azmus.auto_backup")

DAILY_DIR = BACKUP_PATH / "daily"
RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
INCLUDE_UPLOADS = os.getenv("BACKUP_INCLUDE_UPLOADS", "true").lower() in (
    "1",
    "true",
    "yes",
)


def _prune_old_backups(directory: Path, keep_days: int) -> int:
    if not directory.is_dir():
        return 0
    cutoff = datetime.utcnow() - timedelta(days=keep_days)
    removed = 0
    for item in directory.iterdir():
        try:
            mtime = datetime.utcfromtimestamp(item.stat().st_mtime)
        except OSError:
            continue
        if mtime < cutoff:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
            removed += 1
    return removed


def run_daily_backup() -> dict:
    """Create timestamped backup; prune backups older than RETENTION_DAYS."""
    ensure_data_directories()
    DAILY_DIR.mkdir(parents=True, exist_ok=True)

    if not DATABASE_URL.startswith("sqlite"):
        raise RuntimeError("Daily backup supports SQLite only")

    if not DB_PATH.is_file():
        logger.warning("Database file missing at %s — skip backup", DB_PATH)
        return {"status": "skipped", "reason": "no database file"}

    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    db_dest = DAILY_DIR / f"azmus_{stamp}.db"
    shutil.copy2(DB_PATH, db_dest)

    uploads_archive = None
    if INCLUDE_UPLOADS and UPLOAD_PATH.is_dir():
        uploads_archive = DAILY_DIR / f"uploads_{stamp}.zip"
        with zipfile.ZipFile(uploads_archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in UPLOAD_PATH.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(UPLOAD_PATH).as_posix())

    removed = _prune_old_backups(DAILY_DIR, RETENTION_DAYS)

    result = {
        "status": "ok",
        "database_backup": str(db_dest),
        "uploads_backup": str(uploads_archive) if uploads_archive else None,
        "pruned_old_files": removed,
        "retention_days": RETENTION_DAYS,
    }
    logger.info("Daily backup completed: %s", result)
    return result


def restore_database_from_backup(backup_file: Path) -> dict:
    """Restore SQLite DB from a .db backup file (creates pre-restore copy)."""
    backup_file = Path(backup_file).resolve()
    if not backup_file.is_file():
        raise FileNotFoundError(f"Backup not found: {backup_file}")

    ensure_data_directories()
    if DB_PATH.is_file():
        pre = DB_PATH.with_suffix(f".pre_restore_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.db")
        shutil.copy2(DB_PATH, pre)
    else:
        pre = None

    from database import replace_sqlite_database

    replace_sqlite_database(DB_PATH, backup_file)
    return {
        "status": "restored",
        "from": str(backup_file),
        "to": str(DB_PATH),
        "pre_restore_copy": str(pre) if pre else None,
    }
