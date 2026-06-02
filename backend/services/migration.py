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

from sqlalchemy.orm import Session

from constants import NOTIFICATION_EVENTS
from database import DATABASE_URL
from models import MigrationHistory
from routers.uploads_router import UPLOAD_DIR
from services.branding import BRANDING_DB_PREFIX
from services.settings_store import TELEGRAM_KEYS

logger = logging.getLogger("azmus.migration")

MANIFEST_VERSION = 1
BACKUP_RETENTION = 20
MAX_ZIP_MB = int(os.getenv("MIGRATION_MAX_ZIP_MB", "50"))
MIGRATION_BACKUP_ROOT = Path(os.getenv("MIGRATION_BACKUP_DIR", "backups/migrations"))

DB_ARCHIVE_NAME = "database.db"
MANIFEST_NAME = "manifest.json"
UPLOADS_PREFIX = "uploads/"


def _sqlite_db_path() -> Path:
    if not DATABASE_URL.startswith("sqlite"):
        raise ValueError("Migration only supports SQLite databases")
    raw = DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _upload_root() -> Path:
    return Path(UPLOAD_DIR).resolve()


def _count_from_db(db_path: Path) -> dict[str, int]:
    if not db_path.is_file():
        return {}
    conn = sqlite3.connect(str(db_path))
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

        def settings_in(keys: set[str]) -> int:
            if not keys:
                return 0
            placeholders = ",".join("?" for _ in keys)
            try:
                return cur.execute(
                    f"SELECT COUNT(*) FROM system_settings WHERE key IN ({placeholders})",
                    tuple(keys),
                ).fetchone()[0]
            except sqlite3.Error:
                return 0

        notify_keys = {f"notify_{e}" for e in NOTIFICATION_EVENTS}
        notify_keys |= {"notifications_enabled", "telegram_notifications_enabled"}

        return {
            "tasks": count("tasks"),
            "permissions": count("user_permissions"),
            "documents": count("documents"),
            "brand_settings": settings_like(f"{BRANDING_DB_PREFIX}%"),
            "telegram_settings": settings_in(TELEGRAM_KEYS),
            "notification_settings": settings_in(notify_keys),
        }
    finally:
        conn.close()


def _collect_upload_paths(
    upload_root: Path,
    *,
    include_llp: bool,
    include_branding: bool,
) -> list[Path]:
    paths: list[Path] = []
    if include_llp and (upload_root / "llp").is_dir():
        paths.extend(p for p in (upload_root / "llp").iterdir() if p.is_file())
    if include_branding and (upload_root / "branding").is_dir():
        paths.extend(p for p in (upload_root / "branding").iterdir() if p.is_file())
    return paths


def _url_to_local_path(url: str, upload_root: Path) -> Optional[Path]:
    if not url or not url.startswith("/uploads/"):
        return None
    rel = url[len("/uploads/") :]
    return upload_root / rel.replace("/", os.sep)


def verify_data_integrity(db_path: Path, upload_root: Path) -> dict[str, Any]:
    """Post-import verification: DB counts + on-disk files + missing references."""
    counts = _count_from_db(db_path)
    llp_dir = upload_root / "llp"
    branding_dir = upload_root / "branding"
    llp_files = len([p for p in llp_dir.iterdir() if p.is_file()]) if llp_dir.is_dir() else 0
    branding_files = (
        len([p for p in branding_dir.iterdir() if p.is_file()]) if branding_dir.is_dir() else 0
    )

    missing_files: list[str] = []
    if db_path.is_file():
        conn = sqlite3.connect(str(db_path))
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

    return {
        "tasks_count": counts.get("tasks", 0),
        "permissions_count": counts.get("permissions", 0),
        "llp_files_count": llp_files,
        "branding_files_count": branding_files,
        "documents_in_db": counts.get("documents", 0),
        "missing_files_count": len(missing_files),
        "missing_files": missing_files[:20],
        "brand_settings_count": counts.get("brand_settings", 0),
        "telegram_settings_count": counts.get("telegram_settings", 0),
        "notification_settings_count": counts.get("notification_settings", 0),
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
        raise FileNotFoundError("Database file not found")

    upload_root = _upload_root()
    include_db = options.get("include_database", True)
    include_llp = options.get("include_llp_files", True)
    include_branding = options.get("include_branding_files", True)

    counts = _count_from_db(db_path)
    upload_files = _collect_upload_paths(
        upload_root, include_llp=include_llp, include_branding=include_branding
    )

    manifest = {
        "version": MANIFEST_VERSION,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "label": label or "export",
        "options": options,
        "counts": {
            **counts,
            "llp_files": len([p for p in upload_files if "llp" in p.parts]),
            "branding_files": len([p for p in upload_files if "branding" in p.parts]),
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

    with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
        manifest = _parse_manifest_from_zip(zf)
        incoming = manifest.get("counts", {})
        file_list = zf.namelist()
        has_db = DB_ARCHIVE_NAME in file_list

    return {
        "manifest_version": manifest.get("version"),
        "exported_at": manifest.get("exported_at"),
        "label": manifest.get("label", ""),
        "options": manifest.get("options", {}),
        "full_database_replace": has_db,
        "incoming": {
            "tasks": incoming.get("tasks", 0),
            "permissions": incoming.get("permissions", 0),
            "documents": incoming.get("documents", 0),
            "llp_files": incoming.get("llp_files", 0),
            "branding_files": incoming.get("branding_files", 0),
            "brand_settings": incoming.get("brand_settings", 0),
            "telegram_settings": incoming.get("telegram_settings", 0),
            "notification_settings": incoming.get("notification_settings", 0),
        },
        "current": {
            "tasks": current_counts.get("tasks", 0),
            "permissions": current_counts.get("permissions", 0),
            "documents": current_counts.get("documents", 0),
            "llp_files": current_llp,
            "branding_files": current_branding,
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
        shutil.copy2(incoming_db, db_path)

    incoming_uploads = extract_root / "uploads"
    if incoming_uploads.is_dir():
        upload_root.mkdir(parents=True, exist_ok=True)
        for sub in incoming_uploads.iterdir():
            if sub.is_dir():
                target = upload_root / sub.name
                target.mkdir(parents=True, exist_ok=True)
                for f in sub.iterdir():
                    if f.is_file():
                        shutil.copy2(f, target / f.name)

    verification = verify_data_integrity(db_path, upload_root)
    return {
        "manifest": manifest,
        "verification": verification,
    }


def rollback_from_backup(history: MigrationHistory) -> dict[str, Any]:
    if not history.backup_path or not Path(history.backup_path).is_dir():
        raise FileNotFoundError("Backup path not found for this migration run")

    backup_dir = Path(history.backup_path)
    db_bak = backup_dir / "database.db.bak"
    db_path = _sqlite_db_path()
    upload_root = _upload_root()

    if db_bak.is_file():
        shutil.copy2(db_bak, db_path)

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
