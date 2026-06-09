"""Migration bundle export, import, verification, and rollback."""

from __future__ import annotations

import io
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from constants import NOTIFICATION_EVENTS
from database import engine, replace_sqlite_database
from models import MigrationHistory
from routers.uploads_router import UPLOAD_DIR
from services.branding import BRANDING_DB_PREFIX
from services.settings_store import TELEGRAM_KEYS

logger = logging.getLogger("azmus.migration")

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_VERSION = 1
BACKUP_RETENTION = 20
MAX_ZIP_MB = int(os.getenv("MIGRATION_MAX_ZIP_MB", "50"))
from config.paths import MIGRATION_BACKUP_PATH

MIGRATION_BACKUP_ROOT = MIGRATION_BACKUP_PATH

DB_ARCHIVE_NAME = "database.db"
MANIFEST_NAME = "manifest.json"
UPLOADS_PREFIX = "uploads/"


def _sqlite_db_path() -> Path:
    """Resolve the SQLite file the running app actually uses (not cwd-relative)."""
    with engine.connect() as conn:
        rows = conn.execute(sql_text("PRAGMA database_list")).fetchall()
    for row in rows:
        # (seq, name, file)
        if len(row) >= 3 and row[1] == "main" and row[2]:
            return Path(str(row[2])).resolve()
    raise FileNotFoundError("Could not resolve SQLite database path from engine")


def _upload_root() -> Path:
    root = Path(UPLOAD_DIR)
    if not root.is_absolute():
        root = (_BACKEND_ROOT / root).resolve()
    return root.resolve()


def _sqlite_connect(db_path: Path) -> sqlite3.Connection:
    timeout = int(os.getenv("SQLITE_TIMEOUT_SECONDS", "30"))
    return sqlite3.connect(str(db_path), timeout=timeout)


def _table_count(db_path: Path) -> int:
    if not db_path.is_file():
        return 0
    conn = _sqlite_connect(db_path)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
    except sqlite3.Error:
        return 0
    finally:
        conn.close()


def _count_from_db(db_path: Path) -> dict[str, int]:
    if not db_path.is_file():
        return {}
    conn = _sqlite_connect(db_path)
    try:
        cur = conn.cursor()

        def count(table: str) -> int:
            try:
                return cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.Error:
                return 0

        def settings_like(pattern: str) -> int:
            try:
                return cur.execute(
                    "SELECT COUNT(*) FROM system_settings WHERE key LIKE ?",
                    (pattern,),
                ).fetchone()[0]
            except sqlite3.Error:
                return 0

        def settings_in(keys: set[str], *, non_empty: bool = False) -> int:
            if not keys:
                return 0
            placeholders = ",".join("?" for _ in keys)
            sql = f"SELECT COUNT(*) FROM system_settings WHERE key IN ({placeholders})"
            if non_empty:
                sql += " AND value IS NOT NULL AND TRIM(value) != ''"
            try:
                return cur.execute(sql, tuple(keys)).fetchone()[0]
            except sqlite3.Error:
                return 0

        notify_keys = {f"notify_{e}" for e in NOTIFICATION_EVENTS}
        notify_keys |= {"notifications_enabled", "telegram_notifications_enabled"}

        def count_where(table: str, where: str = "") -> int:
            try:
                sql = f"SELECT COUNT(*) FROM {table}"
                if where:
                    sql += f" WHERE {where}"
                return cur.execute(sql).fetchone()[0]
            except sqlite3.Error:
                return 0

        mes = {
            "mes_categories": count_where(
                "mes_product_categories", "is_active = 1"
            ),
            "mes_parts": count_where(
                "mes_product_parts", "is_active = 1 AND deleted_at IS NULL"
            ),
            "mes_templates": count_where(
                "mes_product_templates", "deleted_at IS NULL"
            ),
            "mes_bom_lines": count_where(
                "mes_bom_lines", "is_active = 1 AND deleted_at IS NULL"
            ),
            "mes_routes": count_where(
                "mes_production_routes", "is_active = 1 AND deleted_at IS NULL"
            ),
            "mes_route_steps": count_where("mes_route_steps"),
            "mes_drawings": count_where(
                "mes_product_drawings", "is_active = 1 AND deleted_at IS NULL"
            ),
            "mes_production_jobs": count("mes_production_jobs"),
            "mes_job_bom_lines": count("mes_job_bom_lines"),
            "mes_job_route_steps": count("mes_job_route_steps"),
        }

        return {
            "orders": count("orders"),
            "tasks": count("tasks"),
            "users": count("users"),
            "permissions": count("user_permissions"),
            "documents": count("documents"),
            "brand_settings": settings_like(f"{BRANDING_DB_PREFIX}%"),
            "telegram_settings": settings_in(TELEGRAM_KEYS, non_empty=True),
            "notification_settings": settings_in(notify_keys, non_empty=True),
            **mes,
        }
    finally:
        conn.close()


def _url_to_local_path(url: str, upload_root: Path) -> Optional[Path]:
    if not url or not url.startswith("/uploads/"):
        return None
    rel = url[len("/uploads/") :]
    return upload_root / rel.replace("/", os.sep)


def _collect_db_referenced_files(db_path: Path, upload_root: Path) -> list[Path]:
    """Collect upload files referenced by DB rows (documents, tasks, branding URLs)."""
    found: dict[str, Path] = {}
    if not db_path.is_file():
        return []

    conn = _sqlite_connect(db_path)
    try:
        cur = conn.cursor()
        queries = [
            "SELECT url FROM documents WHERE url IS NOT NULL AND url != ''",
            "SELECT url FROM task_attachments WHERE url IS NOT NULL AND url != ''",
            "SELECT value FROM system_settings WHERE value LIKE '/uploads/%'",
            "SELECT image_url FROM mes_product_templates WHERE image_url IS NOT NULL AND image_url != ''",
            "SELECT drawing_url FROM mes_bom_lines WHERE drawing_url IS NOT NULL AND drawing_url != ''",
            "SELECT url FROM mes_product_drawings WHERE url IS NOT NULL AND url != ''",
        ]
        for query in queries:
            try:
                for (url,) in cur.execute(query):
                    local = _url_to_local_path(str(url), upload_root)
                    if local and local.is_file():
                        found[str(local.resolve())] = local
            except sqlite3.Error:
                pass
    finally:
        conn.close()
    return list(found.values())


def _collect_upload_paths(
    db_path: Path,
    upload_root: Path,
    *,
    include_llp: bool,
    include_branding: bool,
    include_mes: bool,
) -> list[Path]:
    """Directory scan + DB-referenced files for LLP/branding/MES."""
    paths: dict[str, Path] = {}

    if include_llp and (upload_root / "llp").is_dir():
        for p in (upload_root / "llp").iterdir():
            if p.is_file():
                paths[str(p.resolve())] = p

    if include_branding and (upload_root / "branding").is_dir():
        for p in (upload_root / "branding").iterdir():
            if p.is_file():
                paths[str(p.resolve())] = p

    if include_mes and (upload_root / "mes").is_dir():
        for p in (upload_root / "mes").rglob("*"):
            if p.is_file():
                paths[str(p.resolve())] = p

    for p in _collect_db_referenced_files(db_path, upload_root):
        try:
            rel_parts = p.relative_to(upload_root).parts
            if not rel_parts:
                continue
            root = rel_parts[0]
            if include_llp and root == "llp":
                paths[str(p.resolve())] = p
            if include_branding and root == "branding":
                paths[str(p.resolve())] = p
            if include_mes and root == "mes":
                paths[str(p.resolve())] = p
        except ValueError:
            pass

    return list(paths.values())


def build_export_report(db_path: Path, upload_root: Path, upload_files: list[Path]) -> dict[str, Any]:
    counts = _count_from_db(db_path)
    llp_files = len([p for p in upload_files if "llp" in p.parts])
    branding_files = len([p for p in upload_files if "branding" in p.parts])
    mes_files = len([p for p in upload_files if "mes" in p.parts])
    db_size = db_path.stat().st_size if db_path.is_file() else 0

    return {
        "database_path": str(db_path),
        "database_size_bytes": db_size,
        "database_size_kb": round(db_size / 1024, 1),
        "table_count": _table_count(db_path),
        "upload_root": str(upload_root),
        "tasks_count": counts.get("tasks", 0),
        "permissions_count": counts.get("permissions", 0),
        "llp_documents_count": counts.get("documents", 0),
        "llp_files_count": llp_files,
        "branding_files_count": branding_files,
        "mes_files_count": mes_files,
        "brand_settings_count": counts.get("brand_settings", 0),
        "telegram_settings_count": counts.get("telegram_settings", 0),
        "notification_settings_count": counts.get("notification_settings", 0),
        "mes_categories_count": counts.get("mes_categories", 0),
        "mes_parts_count": counts.get("mes_parts", 0),
        "mes_templates_count": counts.get("mes_templates", 0),
        "mes_bom_lines_count": counts.get("mes_bom_lines", 0),
        "mes_routes_count": counts.get("mes_routes", 0),
        "mes_route_steps_count": counts.get("mes_route_steps", 0),
        "mes_drawings_count": counts.get("mes_drawings", 0),
        "mes_diagnostics": {
            "MES Categories": counts.get("mes_categories", 0),
            "MES Parts": counts.get("mes_parts", 0),
            "MES Templates": counts.get("mes_templates", 0),
            "MES BOM": counts.get("mes_bom_lines", 0),
            "MES Routes": counts.get("mes_routes", 0),
            "MES Route Steps": counts.get("mes_route_steps", 0),
            "MES Drawings": counts.get("mes_drawings", 0),
            "MES Files": mes_files,
        },
        "includes_database": db_path.is_file(),
    }


def _collect_mes_urls(db_path: Path) -> list[str]:
    if not db_path.is_file():
        return []
    urls: list[str] = []
    conn = _sqlite_connect(db_path)
    try:
        cur = conn.cursor()
        queries = [
            "SELECT image_url FROM mes_product_templates WHERE image_url IS NOT NULL AND image_url != ''",
            "SELECT drawing_url FROM mes_bom_lines WHERE drawing_url IS NOT NULL AND drawing_url != ''",
            "SELECT url FROM mes_product_drawings WHERE url IS NOT NULL AND url != ''",
        ]
        for query in queries:
            try:
                for (url,) in cur.execute(query):
                    if url:
                        urls.append(str(url))
            except sqlite3.Error:
                pass
    finally:
        conn.close()
    return urls


def verify_data_integrity(db_path: Path, upload_root: Path) -> dict[str, Any]:
    """Post-import verification: DB counts + on-disk files + missing references."""
    counts = _count_from_db(db_path)
    llp_dir = upload_root / "llp"
    branding_dir = upload_root / "branding"
    mes_dir = upload_root / "mes"
    llp_files = len([p for p in llp_dir.iterdir() if p.is_file()]) if llp_dir.is_dir() else 0
    branding_files = (
        len([p for p in branding_dir.iterdir() if p.is_file()]) if branding_dir.is_dir() else 0
    )
    mes_files = len([p for p in mes_dir.rglob("*") if p.is_file()]) if mes_dir.is_dir() else 0

    missing_files: list[str] = []
    if db_path.is_file():
        conn = _sqlite_connect(db_path)
        try:
            cur = conn.cursor()
            try:
                rows = cur.execute("SELECT url FROM documents").fetchall()
                for (url,) in rows:
                    local = _url_to_local_path(url or "", upload_root)
                    if local is None or not local.is_file():
                        missing_files.append(url or "")
            except sqlite3.Error:
                pass

            try:
                rows = cur.execute(
                    "SELECT value FROM system_settings WHERE key LIKE ?",
                    (f"{BRANDING_DB_PREFIX}%",),
                ).fetchall()
                for (value,) in rows:
                    if value and str(value).startswith("/uploads/"):
                        local = _url_to_local_path(str(value), upload_root)
                        if local is None or not local.is_file():
                            missing_files.append(str(value))
            except sqlite3.Error:
                pass
        finally:
            conn.close()

        for url in _collect_mes_urls(db_path):
            local = _url_to_local_path(url, upload_root)
            if local is None or not local.is_file():
                missing_files.append(url)

    return {
        "tasks_count": counts.get("tasks", 0),
        "permissions_count": counts.get("permissions", 0),
        "llp_files_count": llp_files,
        "branding_files_count": branding_files,
        "mes_files_count": mes_files,
        "documents_in_db": counts.get("documents", 0),
        "missing_files_count": len(missing_files),
        "missing_files": missing_files[:20],
        "brand_settings_count": counts.get("brand_settings", 0),
        "telegram_settings_count": counts.get("telegram_settings", 0),
        "notification_settings_count": counts.get("notification_settings", 0),
        "mes_categories_count": counts.get("mes_categories", 0),
        "mes_parts_count": counts.get("mes_parts", 0),
        "mes_templates_count": counts.get("mes_templates", 0),
        "mes_bom_lines_count": counts.get("mes_bom_lines", 0),
        "mes_routes_count": counts.get("mes_routes", 0),
        "mes_route_steps_count": counts.get("mes_route_steps", 0),
        "mes_drawings_count": counts.get("mes_drawings", 0),
        "mes_diagnostics": {
            "MES Categories": counts.get("mes_categories", 0),
            "MES Parts": counts.get("mes_parts", 0),
            "MES Templates": counts.get("mes_templates", 0),
            "MES BOM": counts.get("mes_bom_lines", 0),
            "MES Routes": counts.get("mes_routes", 0),
            "MES Route Steps": counts.get("mes_route_steps", 0),
            "MES Drawings": counts.get("mes_drawings", 0),
            "MES Files": mes_files,
        },
        "ok": len(missing_files) == 0,
    }


def _parse_manifest_from_zip(zf: zipfile.ZipFile) -> dict:
    try:
        raw = zf.read(MANIFEST_NAME).decode("utf-8")
        data = json.loads(raw)
    except (KeyError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid migration bundle: missing or bad {MANIFEST_NAME}") from exc
    if data.get("version") != MANIFEST_VERSION:
        raise ValueError(
            f"Unsupported manifest version {data.get('version')}; expected {MANIFEST_VERSION}"
        )
    return data


def build_export_bundle(options: dict, label: str = "") -> tuple[Path, dict]:
    """Create ZIP on disk; returns path and manifest summary."""
    db_path = _sqlite_db_path()
    if not db_path.is_file():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    upload_root = _upload_root()
    include_db = options.get("include_database", True)
    include_llp = options.get("include_llp_files", True)
    include_branding = options.get("include_branding_files", True)
    include_mes = options.get("include_mes_files", True)

    counts = _count_from_db(db_path)
    upload_files = _collect_upload_paths(
        db_path,
        upload_root,
        include_llp=include_llp,
        include_branding=include_branding,
        include_mes=include_mes,
    )
    export_report = build_export_report(db_path, upload_root, upload_files)

    manifest = {
        "version": MANIFEST_VERSION,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "label": label or "export",
        "options": options,
        "export_report": export_report,
        "counts": {
            **counts,
            "llp_files": len([p for p in upload_files if "llp" in p.parts]),
            "branding_files": len([p for p in upload_files if "branding" in p.parts]),
            "mes_files": len([p for p in upload_files if "mes" in p.parts]),
        },
        "files": [],
    }

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()
    zip_path = Path(tmp.name)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if include_db:
            zf.write(db_path, DB_ARCHIVE_NAME)
        for fpath in upload_files:
            rel = UPLOADS_PREFIX + str(fpath.relative_to(upload_root)).replace("\\", "/")
            zf.write(fpath, rel)
            manifest["files"].append(rel)
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_ZIP_MB:
        zip_path.unlink(missing_ok=True)
        raise ValueError(f"Export exceeds {MAX_ZIP_MB} MB limit ({size_mb:.1f} MB)")

    manifest["zip_size_bytes"] = zip_path.stat().st_size
    return zip_path, manifest


def preview_import_bundle(content: bytes) -> dict[str, Any]:
    """Parse bundle without writing; compare with current environment."""
    current_db = _sqlite_db_path()
    current_counts = _count_from_db(current_db) if current_db.is_file() else {}
    upload_root = _upload_root()
    current_llp = (
        len([p for p in (upload_root / "llp").iterdir() if p.is_file()])
        if (upload_root / "llp").is_dir()
        else 0
    )
    current_branding = (
        len([p for p in (upload_root / "branding").iterdir() if p.is_file()])
        if (upload_root / "branding").is_dir()
        else 0
    )
    current_mes = (
        len([p for p in (upload_root / "mes").rglob("*") if p.is_file()])
        if (upload_root / "mes").is_dir()
        else 0
    )

    with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
        manifest = _parse_manifest_from_zip(zf)
        incoming = manifest.get("counts", {})
        file_list = zf.namelist()
        has_db = DB_ARCHIVE_NAME in file_list
        db_info = zf.getinfo(DB_ARCHIVE_NAME) if has_db else None
        if has_db:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
            try:
                with zf.open(DB_ARCHIVE_NAME) as dbf:
                    tmp.write(dbf.read())
                tmp.close()
                db_counts = _count_from_db(Path(tmp.name))
                incoming = {**incoming, **db_counts}
            finally:
                try:
                    Path(tmp.name).unlink(missing_ok=True)
                except OSError:
                    pass

    return {
        "manifest_version": manifest.get("version"),
        "exported_at": manifest.get("exported_at"),
        "label": manifest.get("label", ""),
        "options": manifest.get("options", {}),
        "export_report": manifest.get("export_report", {}),
        "full_database_replace": has_db,
        "database_in_zip_bytes": db_info.file_size if db_info else 0,
        "incoming": {
            "orders": incoming.get("orders", 0),
            "tasks": incoming.get("tasks", 0),
            "users": incoming.get("users", 0),
            "permissions": incoming.get("permissions", 0),
            "documents": incoming.get("documents", 0),
            "llp_files": incoming.get("llp_files", 0),
            "branding_files": incoming.get("branding_files", 0),
            "mes_files": incoming.get("mes_files", 0),
            "brand_settings": incoming.get("brand_settings", 0),
            "telegram_settings": incoming.get("telegram_settings", 0),
            "notification_settings": incoming.get("notification_settings", 0),
            "mes_categories": incoming.get("mes_categories", 0),
            "mes_parts": incoming.get("mes_parts", 0),
            "mes_templates": incoming.get("mes_templates", 0),
            "mes_bom_lines": incoming.get("mes_bom_lines", 0),
            "mes_routes": incoming.get("mes_routes", 0),
            "mes_route_steps": incoming.get("mes_route_steps", 0),
            "mes_drawings": incoming.get("mes_drawings", 0),
            "mes_production_jobs": incoming.get("mes_production_jobs", 0),
        },
        "current": {
            "orders": current_counts.get("orders", 0),
            "tasks": current_counts.get("tasks", 0),
            "users": current_counts.get("users", 0),
            "permissions": current_counts.get("permissions", 0),
            "documents": current_counts.get("documents", 0),
            "llp_files": current_llp,
            "branding_files": current_branding,
            "mes_files": current_mes,
            "mes_categories": current_counts.get("mes_categories", 0),
            "mes_parts": current_counts.get("mes_parts", 0),
            "mes_templates": current_counts.get("mes_templates", 0),
            "mes_bom_lines": current_counts.get("mes_bom_lines", 0),
            "mes_routes": current_counts.get("mes_routes", 0),
            "mes_route_steps": current_counts.get("mes_route_steps", 0),
            "mes_drawings": current_counts.get("mes_drawings", 0),
            "mes_production_jobs": current_counts.get("mes_production_jobs", 0),
        },
        "bundle_files": len(file_list),
        "warnings": (
            ["To'liq bazani almashtirish (Full DB Replace) amalga oshiriladi"]
            if has_db
            else []
        ),
    }


def _backup_dir_for_run(run_id: int) -> Path:
    path = MIGRATION_BACKUP_ROOT / str(run_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_pre_import_backup(run_id: int) -> Path:
    """Snapshot current DB and uploads before import."""
    backup_dir = _backup_dir_for_run(run_id)
    db_path = _sqlite_db_path()
    if db_path.is_file():
        shutil.copy2(db_path, backup_dir / "database.db.bak")

    upload_root = _upload_root()
    if upload_root.is_dir():
        dest = backup_dir / "uploads"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(
            upload_root,
            dest,
            ignore=shutil.ignore_patterns(".migration-backups"),
        )
    return backup_dir


def _merge_upload_tree(src: Path, dest_root: Path) -> None:
    """Recursively copy extracted uploads (supports mes/templates, mes/drawings, etc.)."""
    if not src.is_dir():
        return
    dest_root.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        if item.is_file():
            rel = item.relative_to(src)
            target = dest_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def _extract_and_import(content: bytes, backup_dir: Path) -> dict:
    db_path = _sqlite_db_path()
    upload_root = _upload_root()

    with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
        manifest = _parse_manifest_from_zip(zf)
        extract_root = backup_dir / "incoming"
        if extract_root.exists():
            shutil.rmtree(extract_root)
        extract_root.mkdir(parents=True)
        zf.extractall(extract_root)

    incoming_db = extract_root / DB_ARCHIVE_NAME
    if incoming_db.is_file():
        replace_sqlite_database(db_path, incoming_db)

    incoming_uploads = extract_root / "uploads"
    if incoming_uploads.is_dir():
        _merge_upload_tree(incoming_uploads, upload_root)

    verification = verify_data_integrity(db_path, upload_root)
    return {
        "manifest": manifest,
        "verification": verification,
    }


def rollback_from_backup(backup_path: str | Path) -> dict[str, Any]:
    backup_dir = Path(backup_path)
    if not backup_dir.is_dir():
        raise FileNotFoundError("Backup path not found for this migration run")

    db_bak = backup_dir / "database.db.bak"
    db_path = _sqlite_db_path()
    upload_root = _upload_root()

    if db_bak.is_file():
        replace_sqlite_database(db_path, db_bak)

    uploads_bak = backup_dir / "uploads"
    if uploads_bak.is_dir():
        for sub in uploads_bak.iterdir():
            if sub.is_dir():
                target = upload_root / sub.name
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(sub, target)

    verification = verify_data_integrity(db_path, upload_root)
    return {"verification": verification}


def prune_old_backups(db: Session) -> int:
    """Keep last BACKUP_RETENTION migration runs that have backup_path."""
    rows = (
        db.query(MigrationHistory)
        .filter(MigrationHistory.backup_path != "")
        .order_by(MigrationHistory.id.desc())
        .all()
    )
    removed = 0
    for row in rows[BACKUP_RETENTION:]:
        path = Path(row.backup_path)
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    return removed


def export_filename() -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"velcore_migration_v{MANIFEST_VERSION}_{ts}.zip"
