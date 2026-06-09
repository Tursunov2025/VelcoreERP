import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from auth.deps import require_admin
from auth.security import verify_password
from database import SessionLocal, get_db
from models import MigrationHistory, User
from schemas import (
    MigrationExportRequest,
    MigrationHistoryResponse,
    MigrationImportResponse,
    MigrationPreviewResponse,
)
from services.audit import log_action
from config.database_guard import DatabaseGuardError, assert_migration_import_allowed
from services.migration import (
    BACKUP_RETENTION,
    MANIFEST_VERSION,
    build_export_bundle,
    create_pre_import_backup,
    export_filename,
    preview_import_bundle,
    prune_old_backups,
    rollback_from_backup,
    _extract_and_import,
)

router = APIRouter(prefix="/admin/migration", tags=["migration"])

MAX_UPLOAD_BYTES = int(os.getenv("MIGRATION_MAX_ZIP_MB", "50")) * 1024 * 1024


def _verify_admin_password(admin: User, password: str) -> None:
    if not password:
        raise HTTPException(status_code=400, detail="Admin parol talab qilinadi")
    if admin.password_hash:
        if not verify_password(password, admin.password_hash):
            raise HTTPException(status_code=403, detail="Admin parol noto'g'ri")
        return
    if admin.password and admin.password != password:
        raise HTTPException(status_code=403, detail="Admin parol noto'g'ri")
    if not admin.password_hash and not admin.password:
        raise HTTPException(status_code=403, detail="Admin parol noto'g'ri")


async def _read_upload(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"ZIP hajmi {MAX_UPLOAD_BYTES // (1024 * 1024)} MB dan oshmasligi kerak",
        )
    return content


@router.post("/export")
def export_migration(
    body: MigrationExportRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    options = {
        "include_database": body.include_database,
        "include_llp_files": body.include_llp_files,
        "include_branding_files": body.include_branding_files,
        "include_mes_files": body.include_mes_files,
        "include_tasks": body.include_tasks,
        "include_permissions": body.include_permissions,
        "include_notification_settings": body.include_notification_settings,
        "include_telegram_settings": body.include_telegram_settings,
    }
    if not body.include_database:
        raise HTTPException(status_code=400, detail="include_database must be true for export")

    try:
        zip_path, manifest = build_export_bundle(options, label=body.label or "")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    export_report = manifest.get("export_report", {})
    history = MigrationHistory(
        username=admin.username,
        action="export",
        status="completed",
        bundle_name=export_filename(),
        manifest_version=MANIFEST_VERSION,
        summary_json=json.dumps(
            {
                "counts": manifest.get("counts", {}),
                "options": options,
                "export_report": export_report,
            }
        ),
        source_env=body.label or "",
        completed_at=datetime.utcnow(),
    )
    db.add(history)
    log_action(
        db,
        admin.username,
        "export",
        "migration",
        details=json.dumps({"export_report": export_report}),
    )
    db.commit()

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=history.bundle_name,
        headers={"X-Migration-Export-Report": json.dumps(export_report)},
    )


@router.post("/preview", response_model=MigrationPreviewResponse)
async def preview_migration(
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
):
    content = await _read_upload(file)
    try:
        preview = preview_import_bundle(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return preview


@router.post("/import", response_model=MigrationImportResponse)
async def import_migration(
    file: UploadFile = File(...),
    admin_password: str = Form(...),
    confirm: str = Form(...),
    admin: User = Depends(require_admin),
):
    if confirm.lower() not in ("true", "1", "yes"):
        raise HTTPException(status_code=400, detail="Import uchun confirm=true kerak")

    _verify_admin_password(admin, admin_password)

    content = await _read_upload(file)
    try:
        preview = preview_import_bundle(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not preview.get("full_database_replace"):
        raise HTTPException(status_code=400, detail="Bundle must contain database.db")

    try:
        assert_migration_import_allowed(preview)
    except DatabaseGuardError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    backup_run_id = int(datetime.utcnow().timestamp())
    backup_dir = create_pre_import_backup(backup_run_id)

    try:
        result = _extract_and_import(content, backup_dir)
        verification = result["verification"]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}") from exc

    db = SessionLocal()
    try:
        history = MigrationHistory(
            username=admin.username,
            action="import",
            status="completed",
            bundle_name=file.filename or "import.zip",
            manifest_version=preview.get("manifest_version") or MANIFEST_VERSION,
            source_env=preview.get("label") or "",
            backup_path=str(backup_dir.resolve()),
            completed_at=datetime.utcnow(),
            summary_json=json.dumps(
                {
                    "preview": preview,
                    "verification": verification,
                    "restart_required": True,
                }
            ),
        )
        db.add(history)
        db.flush()
        prune_old_backups(db)
        log_action(
            db,
            admin.username,
            "import",
            "migration",
            entity_id=history.id,
            details=json.dumps({"verification": verification}),
        )
        db.commit()
        db.refresh(history)
        migration_id = history.id
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}") from exc
    finally:
        db.close()

    return MigrationImportResponse(
        success=True,
        migration_id=migration_id,
        restart_required=True,
        message="Import muvaffaqiyatli. API ni qayta ishga tushiring.",
        verification=verification,
        preview=preview,
        backups_retained=BACKUP_RETENTION,
    )


@router.get("/history", response_model=list[MigrationHistoryResponse])
def migration_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    rows = (
        db.query(MigrationHistory)
        .order_by(MigrationHistory.id.desc())
        .limit(min(limit, 100))
        .all()
    )
    return rows


@router.post("/rollback/{migration_id}", response_model=MigrationImportResponse)
def rollback_migration(
    migration_id: int,
    admin_password: str = Form(...),
    admin: User = Depends(require_admin),
):
    _verify_admin_password(admin, admin_password)

    db = SessionLocal()
    try:
        history = db.query(MigrationHistory).filter(MigrationHistory.id == migration_id).first()
        if not history:
            raise HTTPException(status_code=404, detail="Migration run not found")
        if history.action != "import" or history.status != "completed":
            raise HTTPException(status_code=400, detail="Only completed imports can be rolled back")
        if not history.backup_path:
            raise HTTPException(status_code=400, detail="No backup available for rollback")

        history_id = history.id
        history_backup_path = history.backup_path
        bundle_name = history.bundle_name
        manifest_version = history.manifest_version
    finally:
        db.close()

    try:
        result = rollback_from_backup(history_backup_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    verification = result.get("verification", {})
    admin_username = admin.username

    db = SessionLocal()
    try:
        restored = db.query(MigrationHistory).filter(MigrationHistory.id == history_id).first()
        if restored:
            restored.status = "rolled_back"
        rollback_row = MigrationHistory(
            username=admin_username,
            action="rollback",
            status="completed",
            bundle_name=bundle_name,
            manifest_version=manifest_version,
            backup_path=history_backup_path,
            summary_json=json.dumps(result),
            completed_at=datetime.utcnow(),
        )
        db.add(rollback_row)
        db.flush()
        log_action(
            db,
            admin_username,
            "rollback",
            "migration",
            entity_id=history_id,
            details=json.dumps(verification),
        )
        db.commit()
        db.refresh(rollback_row)
        rollback_id = rollback_row.id
    finally:
        db.close()

    return MigrationImportResponse(
        success=True,
        migration_id=rollback_id,
        restart_required=True,
        message="Rollback bajarildi. API ni qayta ishga tushiring.",
        verification=verification,
        preview=None,
        backups_retained=BACKUP_RETENTION,
    )
