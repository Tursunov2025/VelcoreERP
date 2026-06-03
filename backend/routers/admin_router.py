import os
import shutil
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from auth.deps import require_admin
from auth.security import hash_password
from constants import DEPARTMENTS, PRODUCTION_STAGES
from config.paths import BACKUP_PATH, DB_PATH
from database import DATABASE_URL, get_db
from models import AuditLog, Order, OrderHistory, OrderImage, User, WarehouseItem
from schemas import (
    AdminOrderUpdate,
    AdminUserCreate,
    AdminUserUpdate,
    AuditLogResponse,
    BackupSettingsUpdate,
    BrandingSettingsUpdate,
    CostingSettingsUpdate,
    ExecutiveSettingsUpdate,
    MaterialsSettingsUpdate,
    NotificationSettingsUpdate,
    PasswordResetRequest,
    PermissionsUpdate,
    ProductionSettingsUpdate,
    SettingsImportRequest,
    SystemSettingsUpdate,
    TelegramSettingsUpdate,
    UserAdminResponse,
    WarehouseSettingsUpdate,
)
from services.activity import get_online_operators_detailed
from services.audit import log_action
from services.branding import get_branding, reset_branding, update_branding
from services.permissions import list_all_user_permissions, set_user_permissions
from services.settings_store import (
    export_settings_bundle,
    get_all_settings,
    get_notification_settings,
    get_settings_for_admin,
    get_settings_group,
    get_telegram_settings,
    import_settings_bundle,
    update_notification_settings,
    update_settings_group,
    update_telegram_settings,
)
from services.telegram import send_test_message
from services.task_overdue_reminders import send_overdue_task_reminders

router = APIRouter(prefix="/admin", tags=["admin"])


def _serialize_order(order: Order) -> dict:
    return {
        "id": order.id,
        "client": order.client,
        "phone": order.phone or "",
        "amount": order.amount or "0",
        "comment": order.comment or "",
        "destination": order.destination or "",
        "status": order.status,
        "operator_id": order.operator_id,
        "image_url": order.image_url,
        "in_warehouse": bool(order.in_warehouse),
        "deleted_at": order.deleted_at,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "estimated_finish_at": order.estimated_finish_at,
        "history": [
            {
                "id": h.id,
                "stage": h.stage,
                "operator_username": h.operator_username,
                "action": h.action,
                "comment": h.comment,
                "completed_at": h.completed_at,
            }
            for h in (order.history or [])
        ],
        "images": [{"id": i.id, "url": i.url} for i in (order.images or [])],
    }


# --- Users ---
@router.get("/users", response_model=list[UserAdminResponse])
def admin_list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return db.query(User).order_by(User.username).all()


@router.post("/users", response_model=UserAdminResponse)
def admin_create_user(
    data: AdminUserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if data.department not in DEPARTMENTS:
        raise HTTPException(status_code=400, detail="Invalid department")
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="User already exists")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=data.role,
        department=data.department,
        is_active=data.is_active,
    )
    db.add(user)
    log_action(db, admin.username, "create", "user", details=f"Created {data.username}")
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=UserAdminResponse)
def admin_update_user(
    user_id: int,
    data: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if data.username is not None:
        user.username = data.username
    if data.role is not None:
        user.role = data.role
    if data.department is not None:
        if data.department not in DEPARTMENTS:
            raise HTTPException(status_code=400, detail="Invalid department")
        user.department = data.department
    if data.is_active is not None:
        user.is_active = data.is_active

    log_action(db, admin.username, "update", "user", user_id, f"Updated {user.username}")
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username == admin.username:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    name = user.username
    db.delete(user)
    log_action(db, admin.username, "delete", "user", user_id, f"Deleted {name}")
    db.commit()
    return {"message": "User deleted"}


@router.post("/users/{user_id}/reset-password")
def admin_reset_password(
    user_id: int,
    data: PasswordResetRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(data.password)
    user.password = None
    log_action(db, admin.username, "reset_password", "user", user_id, user.username)
    db.commit()
    return {"message": "Password updated"}


# --- Orders ---
@router.get("/orders/search")
def admin_search_orders(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    client: str = Query(""),
    operator: str = Query(""),
    stage: str = Query(""),
    department: str = Query(""),
    status: str = Query(""),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    include_deleted: bool = Query(False),
):
    query = db.query(Order).options(
        joinedload(Order.history),
        joinedload(Order.images),
    )

    if include_deleted:
        query = query.filter(Order.deleted_at.isnot(None))
    else:
        query = query.filter(Order.deleted_at.is_(None))

    if client.strip():
        query = query.filter(Order.client.ilike(f"%{client}%"))
    if stage.strip():
        query = query.filter(Order.status == stage)
    elif department.strip():
        query = query.filter(Order.status == department)
    elif status.strip():
        query = query.filter(Order.status == status)

    if date_from:
        try:
            dt = datetime.fromisoformat(date_from.replace("Z", ""))
            query = query.filter(Order.created_at >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to.replace("Z", ""))
            query = query.filter(Order.created_at <= dt)
        except ValueError:
            pass

    orders = query.order_by(Order.id.desc()).limit(200).all()

    if operator.strip():
        op_lower = operator.lower()
        filtered = []
        for order in orders:
            if any(
                op_lower in (h.operator_username or "").lower()
                for h in (order.history or [])
            ):
                filtered.append(order)
        orders = filtered

    return [_serialize_order(o) for o in orders]


@router.put("/orders/{order_id}")
def admin_update_order(
    order_id: int,
    data: AdminOrderUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    order = (
        db.query(Order)
        .options(joinedload(Order.history), joinedload(Order.images))
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    old_status = order.status
    for field in (
        "client",
        "phone",
        "amount",
        "comment",
        "destination",
        "status",
        "estimated_finish_at",
    ):
        val = getattr(data, field, None)
        if val is not None:
            setattr(order, field, val)

    order.updated_at = datetime.utcnow()

    if data.status and data.status != old_status:
        if data.status not in PRODUCTION_STAGES:
            raise HTTPException(status_code=400, detail="Invalid stage")
        db.add(
            OrderHistory(
                order_id=order.id,
                stage=data.status,
                operator_username=admin.username,
                action="admin_status_change",
                comment=f"Admin changed: {old_status} → {data.status}",
            )
        )

    log_action(
        db,
        admin.username,
        "update",
        "order",
        order_id,
        f"Admin edited order #{order_id}",
    )
    db.commit()
    db.refresh(order)
    return _serialize_order(order)


@router.delete("/orders/{order_id}")
def admin_soft_delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.deleted_at = datetime.utcnow()
    log_action(db, admin.username, "delete", "order", order_id, f"Soft deleted #{order_id}")
    db.commit()
    return {"message": "Order moved to trash"}


@router.post("/orders/{order_id}/restore")
def admin_restore_order(
    order_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.deleted_at = None
    log_action(db, admin.username, "restore", "order", order_id, f"Restored #{order_id}")
    db.commit()
    return {"message": "Order restored"}


# --- Central system settings (Phase 5) ---
@router.get("/settings/system")
def get_system_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return get_all_settings(db)


@router.get("/settings/company")
def get_company_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return get_settings_group(db, "company")


@router.put("/settings/company")
def put_company_settings(
    data: SystemSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = update_settings_group(db, "company", data.model_dump(exclude_none=True))
    log_action(db, admin.username, "update", "settings", details="Company settings updated")
    db.commit()
    return result


@router.get("/settings/production")
def get_production_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return get_settings_group(db, "production")


@router.put("/settings/production")
def put_production_settings(
    data: ProductionSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = update_settings_group(db, "production", data.model_dump(exclude_none=True))
    log_action(db, admin.username, "update", "settings", details="Production settings updated")
    db.commit()
    return result


@router.get("/settings/warehouse")
def get_warehouse_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return get_settings_group(db, "warehouse")


@router.put("/settings/warehouse")
def put_warehouse_settings(
    data: WarehouseSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = update_settings_group(db, "warehouse", data.model_dump(exclude_none=True))
    log_action(db, admin.username, "update", "settings", details="Warehouse settings updated")
    db.commit()
    return result


@router.get("/settings/materials")
def get_materials_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return get_settings_group(db, "materials")


@router.put("/settings/materials")
def put_materials_settings(
    data: MaterialsSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = update_settings_group(db, "materials", data.model_dump(exclude_none=True))
    log_action(db, admin.username, "update", "settings", details="Materials settings updated")
    db.commit()
    return result


@router.get("/settings/costing")
def get_costing_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return get_settings_group(db, "costing")


@router.put("/settings/costing")
def put_costing_settings(
    data: CostingSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = update_settings_group(db, "costing", data.model_dump(exclude_none=True))
    log_action(db, admin.username, "update", "settings", details="Costing settings updated")
    db.commit()
    return result


@router.get("/settings/backup")
def get_backup_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return get_settings_group(db, "backup")


@router.put("/settings/backup")
def put_backup_settings(
    data: BackupSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = update_settings_group(db, "backup", data.model_dump(exclude_none=True))
    log_action(db, admin.username, "update", "settings", details="Backup settings updated")
    db.commit()
    return result


@router.get("/settings/executive")
def get_executive_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return get_settings_group(db, "executive")


@router.put("/settings/executive")
def put_executive_settings(
    data: ExecutiveSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = update_settings_group(db, "executive", data.model_dump(exclude_none=True))
    log_action(db, admin.username, "update", "settings", details="Executive control center settings updated")
    db.commit()
    return result


@router.get("/settings/export")
def export_settings(
    include_branding: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    bundle = export_settings_bundle(db, include_branding=include_branding)
    return bundle


@router.post("/settings/import")
def import_settings(
    data: SettingsImportRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        result = import_settings_bundle(db, data.settings, merge=data.merge)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_action(db, admin.username, "import", "settings", details="Settings bundle imported")
    db.commit()
    return {"message": "Settings imported", "settings": result}


@router.put("/settings/system")
def put_system_settings(
    data: SystemSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    update_settings_group(db, "company", data.model_dump(exclude_none=True))
    log_action(db, admin.username, "update", "settings", details="System settings updated")
    db.commit()
    return get_all_settings(db)


# --- Online users ---
@router.get("/operators/online")
def admin_online_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return {"operators": get_online_operators_detailed(db)}


# --- Audit logs ---
@router.get("/audit-logs", response_model=list[AuditLogResponse])
def list_audit_logs(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    limit: int = Query(200, le=1000),
    q: str = Query(""),
    action: str = Query(""),
    entity_type: str = Query(""),
    username: str = Query(""),
):
    query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if username:
        query = query.filter(AuditLog.username.ilike(f"%{username}%"))
    logs = query.limit(limit).all()
    if q:
        q_lower = q.lower()
        logs = [
            log
            for log in logs
            if q_lower in (log.details or "").lower()
            or q_lower in (log.entity_type or "").lower()
            or q_lower in (log.username or "").lower()
            or q_lower in (log.action or "").lower()
        ]
    return logs


# --- Backup ---
@router.get("/backup/export")
def export_backup(
    _: User = Depends(require_admin),
):
    if not DATABASE_URL.startswith("sqlite"):
        raise HTTPException(status_code=400, detail="Backup only supported for SQLite")

    db_path = str(DB_PATH)
    if not DB_PATH.is_file():
        raise HTTPException(status_code=404, detail="Database file not found")

    backup_dir = BACKUP_PATH / "manual"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_name = f"azmus_backup_{timestamp}.db"
    backup_path = backup_dir / backup_name
    shutil.copy2(db_path, backup_path)

    return FileResponse(
        backup_path,
        media_type="application/octet-stream",
        filename=backup_name,
    )


@router.post("/backup/import")
async def import_backup(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if not DATABASE_URL.startswith("sqlite"):
        raise HTTPException(status_code=400, detail="Import only supported for SQLite")

    db_path = str(DB_PATH)
    content = await file.read()

    pre_backup = str(DB_PATH) + ".pre_import.bak"
    if DB_PATH.is_file():
        shutil.copy2(db_path, pre_backup)

    with open(db_path, "wb") as f:
        f.write(content)

    log_action(db, admin.username, "import", "backup", details=file.filename or "backup.db")
    db.commit()
    return {"message": "Backup imported. Restart API to apply fully."}


# --- Permissions ---
@router.get("/permissions")
def get_permissions_matrix(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return {"users": list_all_user_permissions(db)}


@router.put("/permissions/{user_id}")
def update_user_permissions(
    user_id: int,
    data: PermissionsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        perms = set_user_permissions(db, user_id, data.permissions)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    log_action(db, admin.username, "update", "permissions", user_id, target.username)
    db.commit()
    return {"user_id": user_id, "permissions": perms}


# --- Telegram settings ---
@router.get("/settings/telegram")
def get_telegram_settings_endpoint(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return get_telegram_settings(db)


@router.put("/settings/telegram")
def put_telegram_settings(
    data: TelegramSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    payload = data.model_dump(exclude_none=True)
    result = update_telegram_settings(db, payload)
    log_action(db, admin.username, "update", "telegram_settings")
    return result


@router.post("/settings/telegram/test")
async def test_telegram(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await send_test_message(db)
    log_action(
        db,
        admin.username,
        "test",
        "telegram",
        details="ok" if result.get("ok") else result.get("error", ""),
    )
    db.commit()
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Test failed"))
    return result


# --- Notification settings ---
@router.get("/settings/notifications")
def get_notifications_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return get_notification_settings(db)


@router.put("/settings/notifications")
def put_notifications_settings(
    data: NotificationSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    payload = data.model_dump(exclude_none=True)
    result = update_notification_settings(db, payload)
    log_action(db, admin.username, "update", "notification_settings")
    return result


# --- Branding / appearance ---
@router.get("/settings/branding")
def get_branding_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return get_branding(db)


@router.put("/settings/branding")
def put_branding_settings(
    data: BrandingSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    payload = data.model_dump(exclude_none=True)
    result = update_branding(db, payload)
    log_action(db, admin.username, "update", "branding_settings")
    return result


@router.post("/settings/branding/reset")
def reset_branding_settings(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = reset_branding(db)
    log_action(db, admin.username, "reset", "branding_settings")
    return result


@router.post("/reminders/overdue/run")
async def run_overdue_reminders_now(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await send_overdue_task_reminders(db)
    log_action(
        db,
        admin.username,
        "run",
        "overdue_reminders",
        details=f"sent={result['sent']} skipped={result['skipped']}",
    )
    db.commit()
    return result
