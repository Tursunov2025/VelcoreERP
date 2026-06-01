from sqlalchemy.orm import Session

from constants import ALL_PERMISSION_KEYS, DEFAULT_OPERATOR_PERMISSIONS, LLP_PERMISSIONS
from models import User, UserPermission


def _is_admin(user: User) -> bool:
    return user.role == "admin" or user.department == "Admin"


def get_user_permissions(db: Session, user: User) -> dict[str, bool]:
    if _is_admin(user):
        return {key: True for key in ALL_PERMISSION_KEYS}

    rows = (
        db.query(UserPermission)
        .filter(UserPermission.user_id == user.id)
        .all()
    )
    perms = dict(DEFAULT_OPERATOR_PERMISSIONS)
    if user.department == "Ombor":
        perms["warehouse"] = True

    for row in rows:
        if row.module in ALL_PERMISSION_KEYS:
            perms[row.module] = bool(row.enabled)

    return perms


def user_has_permission(db: Session, user: User, key: str) -> bool:
    if _is_admin(user):
        return True
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
