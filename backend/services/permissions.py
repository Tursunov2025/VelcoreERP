from sqlalchemy.orm import Session

from constants import ALL_PERMISSION_KEYS, DEFAULT_OPERATOR_PERMISSIONS, LLP_PERMISSIONS, MES_PERMISSIONS
from models import Role, RolePermission, User, UserPermission


def require_project_job_permission(db: Session, user: User, job, key: str) -> None:
    """Require the project-side half of a terminal permission intersection.

    Terminal routers continue to enforce their own MES permission. Standalone
    jobs deliberately bypass this additional project-only gate.
    """
    if not getattr(job, "project_id", None):
        return
    from fastapi import HTTPException
    if not user_has_permission(db, user, key):
        raise HTTPException(
            status_code=403,
            detail={"code": "permission_denied", "message": f"Permission required: {key}"},
        )
    if getattr(getattr(job, "project", None), "status", None) == "cancelled":
        raise HTTPException(
            status_code=409,
            detail={"code": "project_cancelled", "message": "Cancelled project cannot accept terminal work"},
        )
    return


def _is_root(user: User) -> bool:
    """Only the protected super-admin role is an unconditional bypass."""
    return user.role == "super_admin"


def get_user_permissions(db: Session, user: User) -> dict[str, bool]:
    if _is_root(user):
        return {key: True for key in ALL_PERMISSION_KEYS}

    rows = (
        db.query(UserPermission)
        .filter(UserPermission.user_id == user.id)
        .all()
    )
    role = db.query(Role).filter(Role.role_key == user.role).first()
    role_rows = (
        db.query(RolePermission).filter(RolePermission.role_id == role.id).all()
        if role
        else []
    )

    # Compatibility for a database that has not run the canonical role seed
    # yet. Once Admin has persisted rows, those rows are authoritative.
    if user.role == "admin" and not role_rows:
        perms = {key: True for key in ALL_PERMISSION_KEYS}
    else:
        perms = dict(DEFAULT_OPERATOR_PERMISSIONS)
    if user.department == "Ombor":
        perms["warehouse"] = True

    for role_permission in role_rows:
        if role_permission.permission_key in ALL_PERMISSION_KEYS:
            perms[role_permission.permission_key] = bool(role_permission.enabled)

    # Explicit per-user grants/denials intentionally override role defaults.
    for row in rows:
        if row.module in ALL_PERMISSION_KEYS:
            perms[row.module] = bool(row.enabled)

    return perms


def user_has_permission(db: Session, user: User, key: str) -> bool:
    if _is_root(user):
        return True

    # Terminal access is deliberately NOT granted by ordinary
    # mes_terminal_* user/role permissions. Non-admin terminal access
    # comes from the active brigade -> terminal assignment, where only
    # the brigade leader (brigadier) is authorized.
    if key.startswith("mes_terminal_"):
        return user.role == "admin" or user.department == "Admin"

    return bool(get_user_permissions(db, user).get(key, False))


def user_can_access_module(db: Session, user: User, module: str) -> bool:
    return user_has_permission(db, user, module)


def set_user_permissions(db: Session, user_id: int, permissions: dict[str, bool]) -> dict[str, bool]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    existing = {
        row.module: row
        for row in db.query(UserPermission)
        .filter(UserPermission.user_id == user_id)
        .all()
    }

    for key in ALL_PERMISSION_KEYS:
        if key not in permissions:
            continue
        enabled = bool(permissions[key])
        if key in existing:
            existing[key].enabled = enabled
        else:
            db.add(UserPermission(user_id=user_id, module=key, enabled=enabled))

    db.flush()
    return get_user_permissions(db, user)


def list_all_user_permissions(db: Session) -> list[dict]:
    users = db.query(User).order_by(User.username).all()
    result = []
    for user in users:
        result.append(
            {
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
                "department": user.department,
                "telegram_username": user.telegram_username,
                "telegram_id": user.telegram_id,
                "permissions": get_user_permissions(db, user),
            }
        )
    return result


def list_llp_permission_keys() -> list[str]:
    return list(LLP_PERMISSIONS)


def list_mes_permission_keys() -> list[str]:
    return list(MES_PERMISSIONS)
