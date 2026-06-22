"""
Production data paths — all business data lives outside the application folder.

Configure via .env (see deploy/enterprise/env.production.example):
  DATA_ROOT, DB_PATH, UPLOAD_PATH, BACKUP_PATH, LOG_PATH, MIGRATION_BACKUP_PATH

DATABASE_URL is resolved once here — all modules import from config.paths.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from config.env_loader import get_database_url_source, load_environment

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent

load_environment()

if sys.platform != "win32":
    _DEFAULT_DATA_ROOT = Path("/var/lib/velcore/data")
else:
    _DEFAULT_DATA_ROOT = Path(r"D:\AzmusERP\Data")

DATA_ROOT = Path(os.getenv("DATA_ROOT", str(_DEFAULT_DATA_ROOT))).resolve()
DB_PATH = Path(
    os.getenv(
        "DB_PATH",
        str(DATA_ROOT / "database" / "azmus.db"),
    )
).resolve()
UPLOAD_PATH = Path(
    os.getenv(
        "UPLOAD_PATH",
        str(DATA_ROOT / "uploads"),
    )
).resolve()
BACKUP_PATH = Path(
    os.getenv(
        "BACKUP_PATH",
        str(DATA_ROOT / "backups"),
    )
).resolve()
LOG_PATH = Path(
    os.getenv(
        "LOG_PATH",
        str(DATA_ROOT / "logs"),
    )
).resolve()
MIGRATION_BACKUP_PATH = Path(
    os.getenv(
        "MIGRATION_BACKUP_PATH",
        str(DATA_ROOT / "migrations"),
    )
).resolve()


def ensure_data_directories() -> None:
    """Create production data folders if missing (never creates the .db file)."""
    for folder in (
        DATA_ROOT,
        DB_PATH.parent,
        UPLOAD_PATH,
        BACKUP_PATH,
        BACKUP_PATH / "daily",
        LOG_PATH,
        MIGRATION_BACKUP_PATH,
    ):
        folder.mkdir(parents=True, exist_ok=True)


def sqlite_database_url() -> str:
    ensure_data_directories()
    return f"sqlite:///{DB_PATH.as_posix()}"


def resolve_sqlite_file_from_url(database_url: str) -> Path:
    if not database_url.startswith("sqlite"):
        raise ValueError("Only SQLite URLs are supported")
    raw = database_url.replace("sqlite:///", "").replace("sqlite://", "")
    return Path(raw).resolve()


def resolve_database_url() -> tuple[str, str]:
    """Return (DATABASE_URL, source description). Single resolution point."""
    raw = (os.getenv("DATABASE_URL") or "").strip()
    if raw:
        return raw, get_database_url_source()
    url = sqlite_database_url()
    return url, f"sqlite default ({DB_PATH})"


DATABASE_URL, DATABASE_URL_SOURCE = resolve_database_url()

ensure_data_directories()


def warn_if_non_production_db_path() -> None:
    """Log when configured DB is not the canonical Windows production path."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    import logging

    canonical = Path(r"D:\AzmusERP\Data\database\azmus.db")
    forbidden_names = {"azmus_new.db", "database.db", "app.db", "sqlite.db"}
    name = DB_PATH.name.lower()
    log = logging.getLogger("azmus.paths")
    try:
        backend = _BACKEND_DIR.resolve()
        if name in forbidden_names or (
            DB_PATH.resolve().parent == backend and name.endswith(".db")
        ):
            log.error(
                "DB_PATH %s is inside the application folder — use %s for production",
                DB_PATH,
                canonical,
            )
        elif os.name == "nt" and DB_PATH.resolve() != canonical.resolve() and canonical.drive:
            log.warning(
                "DB_PATH %s is not canonical production path %s",
                DB_PATH,
                canonical,
            )
    except OSError:
        pass


warn_if_non_production_db_path()
