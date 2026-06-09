"""
Production database protection — never silently switch to an empty SQLite file.

Canonical local production path:
  D:\\AzmusERP\\Data\\database\\azmus.db
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

from config.paths import (
    DATABASE_URL,
    DB_PATH,
    DATA_ROOT,
    _BACKEND_DIR,
    _REPO_ROOT,
    resolve_sqlite_file_from_url,
)

_log = logging.getLogger("azmus.database_guard")

CANONICAL_WINDOWS_DB = Path(r"D:\AzmusERP\Data\database\azmus.db")

FORBIDDEN_DB_FILENAMES = frozenset(
    {
        "azmus_new.db",
        "database.db",
        "app.db",
        "sqlite.db",
        "test.db",
    }
)

BASELINE_DEFAULTS: dict[str, int] = {
    "orders": 3,
    "tasks": 4,
    "documents": 5,
    "mes_production_jobs": 10,
    "users": 9,
}


class DatabaseGuardError(RuntimeError):
    """Startup or import blocked to protect production data."""


def _env_truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _baseline() -> dict[str, int]:
    mapping = {
        "orders": "BASELINE_ORDERS",
        "tasks": "BASELINE_TASKS",
        "documents": "BASELINE_DOCUMENTS",
        "mes_production_jobs": "BASELINE_MES_JOBS",
        "users": "BASELINE_USERS",
    }
    out: dict[str, int] = {}
    for key, env_name in mapping.items():
        raw = os.getenv(env_name, str(BASELINE_DEFAULTS[key])).strip()
        try:
            out[key] = max(0, int(raw))
        except ValueError:
            out[key] = BASELINE_DEFAULTS[key]
    return out


def is_guard_enabled() -> bool:
    explicit = os.getenv("DATABASE_GUARD", "").strip()
    if explicit.lower() == "false":
        return False
    if explicit and _env_truthy("DATABASE_GUARD", explicit):
        return True
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    url = os.getenv("DATABASE_URL", "")
    if "test_" in url.lower() or "/temp/" in url.lower() or "\\temp\\" in url.lower():
        return False
    if _env_truthy("PRODUCTION") or os.getenv("ENVIRONMENT", "").lower() in ("production", "prod"):
        return True
    if _env_truthy("SKIP_DEMO_SEED"):
        return True
    try:
        if DB_PATH.resolve() == CANONICAL_WINDOWS_DB.resolve():
            return True
    except OSError:
        pass
    return False


def is_forbidden_database_path(path: Path) -> bool:
    resolved = path.resolve()
    name = resolved.name.lower()
    if name in FORBIDDEN_DB_FILENAMES:
        return True
    try:
        backend = _BACKEND_DIR.resolve()
        repo = _REPO_ROOT.resolve()
        if backend in resolved.parents or resolved.parent == backend:
            return name.endswith(".db")
        if resolved.parent == repo and name.endswith(".db"):
            return True
    except OSError:
        pass
    return False


def _count_table(conn: sqlite3.Connection, table: str) -> int:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return 0


def collect_database_stats(db_path: Path | None = None) -> dict[str, Any]:
    path = (db_path or DB_PATH).resolve()
    stats: dict[str, Any] = {
        "active_database_path": str(path),
        "database_exists": path.is_file(),
        "database_size": 0,
        "table_count": 0,
        "orders_count": 0,
        "tasks_count": 0,
        "documents_count": 0,
        "mes_jobs_count": 0,
        "users_count": 0,
        "guard_enabled": is_guard_enabled(),
        "baseline": _baseline(),
    }
    if not path.is_file():
        return stats

    stats["database_size"] = path.stat().st_size
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        stats["table_count"] = len(tables)
        stats["orders_count"] = _count_table(conn, "orders")
        stats["tasks_count"] = _count_table(conn, "tasks")
        stats["documents_count"] = _count_table(conn, "documents")
        stats["mes_jobs_count"] = _count_table(conn, "mes_production_jobs")
        stats["users_count"] = _count_table(conn, "users")
    finally:
        conn.close()
    return stats


def _assert_url_matches_path() -> None:
    try:
        url_path = resolve_sqlite_file_from_url(DATABASE_URL)
    except ValueError as exc:
        raise DatabaseGuardError(f"Invalid DATABASE_URL: {exc}") from exc
    if url_path.resolve() != DB_PATH.resolve():
        raise DatabaseGuardError(
            "DATABASE_URL and DB_PATH point to different files: "
            f"DATABASE_URL={url_path} DB_PATH={DB_PATH}"
        )


def _check_baseline_counts(stats: dict[str, Any], *, context: str) -> list[str]:
    baseline = _baseline()
    field_map = {
        "orders": "orders_count",
        "tasks": "tasks_count",
        "documents": "documents_count",
        "mes_production_jobs": "mes_jobs_count",
        "users": "users_count",
    }
    warnings: list[str] = []
    for key, field in field_map.items():
        minimum = baseline.get(key, 0)
        if minimum <= 0:
            continue
        actual = int(stats.get(field, 0))
        if actual < minimum:
            msg = f"{context}: {key} count {actual} is below production baseline {minimum}"
            warnings.append(msg)
            _log.warning(msg)
    return warnings


def validate_production_database_at_startup() -> dict[str, Any]:
    stats = collect_database_stats()
    if not is_guard_enabled():
        _log.info("Database guard disabled")
        return stats

    _log.info(
        "Database guard active: DB_PATH=%s DATA_ROOT=%s",
        DB_PATH,
        DATA_ROOT,
    )

    if is_forbidden_database_path(DB_PATH):
        raise DatabaseGuardError(
            f"Refusing application-folder database: {DB_PATH}. "
            f"Use production path {CANONICAL_WINDOWS_DB}"
        )

    _assert_url_matches_path()

    if not DB_PATH.is_file():
        raise DatabaseGuardError(
            f"Production database not found at {DB_PATH}. "
            "Startup aborted — will NOT create a new empty database."
        )

    if stats["table_count"] < 5:
        raise DatabaseGuardError(
            f"Database at {DB_PATH} has only {stats['table_count']} tables. "
            "Refusing startup on empty/invalid database."
        )

    below = _check_baseline_counts(stats, context="Startup")
    if below:
        raise DatabaseGuardError(
            "Production database below baseline. " + "; ".join(below)
        )

    _log.info(
        "Database guard OK: orders=%s tasks=%s llp=%s mes_jobs=%s users=%s",
        stats["orders_count"],
        stats["tasks_count"],
        stats["documents_count"],
        stats["mes_jobs_count"],
        stats["users_count"],
    )
    return stats


def get_database_health() -> dict[str, Any]:
    stats = collect_database_stats()
    return {
        "active_database_path": stats["active_database_path"],
        "database_size": stats["database_size"],
        "table_count": stats["table_count"],
        "orders_count": stats["orders_count"],
        "mes_jobs_count": stats["mes_jobs_count"],
        "database_guard_enabled": stats["guard_enabled"],
        "database_baseline": stats["baseline"],
    }


def migration_import_override_requested() -> bool:
    return _env_truthy("MIGRATION_IMPORT_OVERRIDE")


def assert_migration_import_allowed(preview: dict[str, Any]) -> None:
    if not is_guard_enabled() or not preview.get("full_database_replace"):
        return
    if migration_import_override_requested():
        _log.warning("MIGRATION_IMPORT_OVERRIDE=true — skipping import baseline check")
        return

    incoming = preview.get("incoming") or {}
    incoming_stats = {
        "orders_count": incoming.get("orders", 0),
        "tasks_count": incoming.get("tasks", 0),
        "documents_count": incoming.get("documents", 0),
        "mes_jobs_count": incoming.get("mes_production_jobs", 0),
        "users_count": incoming.get("users", 0),
    }
    warnings = _check_baseline_counts(
        incoming_stats, context="Migration import (incoming bundle)"
    )
    if warnings:
        raise DatabaseGuardError(
            "Migration import refused: incoming bundle below production baseline. "
            + "; ".join(warnings)
        )

    current = preview.get("current") or {}
    current_stats = collect_database_stats()
    if not _check_baseline_counts(current_stats, context="Migration import (current DB)"):
        current_total = (
            current.get("documents", 0)
            + current.get("tasks", 0)
            + current.get("mes_production_jobs", 0)
        )
        incoming_total = (
            incoming.get("documents", 0)
            + incoming.get("tasks", 0)
            + incoming.get("mes_production_jobs", 0)
        )
        if incoming_total < current_total:
            raise DatabaseGuardError(
                "Migration import refused: incoming bundle has fewer records than current production database."
            )


def list_known_database_paths_in_repo() -> list[str]:
    """Audit helper — SQLite files referenced in repo (not necessary on disk)."""
    root = _REPO_ROOT
    patterns = [
        "azmus_new.db",
        "database.db",
        "app.db",
        "sqlite.db",
        "azmus.db",
    ]
    found: list[str] = []
    for pattern in patterns:
        for path in root.rglob(pattern):
            if "node_modules" in path.parts or ".venv" in path.parts:
                continue
            found.append(str(path.resolve()))
    return sorted(set(found))
