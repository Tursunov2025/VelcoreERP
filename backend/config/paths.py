"""
Production data paths — all business data lives outside the application folder.

Configure via .env (see deploy/.env.production.template):
  DATA_ROOT, DB_PATH, UPLOAD_PATH, BACKUP_PATH, LOG_PATH, MIGRATION_BACKUP_PATH
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent


def _load_env_files() -> None:
    explicit = os.getenv("AZMUS_ENV_FILE", "").strip()
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend(
        [
            Path("/etc/velcore/.env"),
            Path("/etc/azmus/.env"),
            _BACKEND_DIR / ".env",
            _REPO_ROOT / ".env",
            Path(r"D:\AzmusERP\Application\.env"),
            Path(r"D:\AzmusERP\.env"),
            Path(r"D:\AzmusERP\Application\backend\.env"),
        ]
    )
    for path in candidates:
        if path.is_file():
            load_dotenv(path, override=False)
            return
    load_dotenv(_BACKEND_DIR / ".env", override=False)
    load_dotenv(_REPO_ROOT / ".env", override=False)


_load_env_files()

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


def warn_if_non_production_db_path() -> None:
    """Log when configured DB is not the canonical Windows production path."""
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
        elif DB_PATH.resolve() != canonical.resolve() and canonical.drive:
            log.warning(
                "DB_PATH %s is not canonical production path %s",
                DB_PATH,
                canonical,
            )
    except OSError:
        pass


def sqlite_database_url() -> str:
    ensure_data_directories()
    return f"sqlite:///{DB_PATH.as_posix()}"


def resolve_sqlite_file_from_url(database_url: str) -> Path:
    if not database_url.startswith("sqlite"):
        raise ValueError("Only SQLite URLs are supported")
    raw = database_url.replace("sqlite:///", "").replace("sqlite://", "")
    return Path(raw).resolve()


# Resolved once at import (after .env load).
DATABASE_URL = os.getenv("DATABASE_URL") or sqlite_database_url()

ensure_data_directories()
warn_if_non_production_db_path()
