import json
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from auth.security import hash_password
from database import get_db
from models import AuditLog, Role, SystemSetting, User, UserIdentityActivity, UserIdentityProfile, UserIdentitySession
from services.permissions import user_has_permission
from services.platform_administration import append_audit, get_versioned_setting
from services.settings_cache import invalidate_settings_cache
from services.settings_runtime import get_departments

router = APIRouter(prefix="/admin/identity", tags=["enterprise identity"])


def require_identity(permission: str):
    def dependency(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> User:
        if user.role != "super_admin" and not user_has_permission(db, user, permission):
            raise HTTPException(403, {"code": "permission_denied", "message": f"Permission required: {permission}"})
        return user
    return dependency


def _audit_context(request: Request) -> dict[str, str]:
    return {"ip_address": request.client.host if request.client else "", "correlation_id": request.headers.get("x-request-id", "")[:128]}


class UserIdentityPayload(BaseModel):
    username: str = Field(min_length=2, max_length=100)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: str = "operator"
    department: str = ""
    full_name: str = ""
    employee_id: str = ""
    position: str = ""
    phone: str = ""
    email: str = ""
    telegram: str = ""
    avatar_url: str = ""
    is_active: bool = True


class DepartmentPayload(BaseModel):
    name: str = Field(min_length=2, max_length=100)


def _profile(db: Session, user_id: int) -> UserIdentityProfile:
    profile = db.query(UserIdentityProfile).filter(UserIdentityProfile.user_id == user_id).first()
    if not profile:
        profile = UserIdentityProfile(user_id=user_id)
        db.add(profile)
        db.flush()
    return profile


def _record(db: Session, user_id: int, action: str, actor: str, details: str = ""):
    db.add(UserIdentityActivity(user_id=user_id, action=action, actor_username=actor, details=details))


def _validate_role(db: Session, role_key: str) -> None:
    if not db.query(Role).filter(Role.role_key == role_key).first():
        raise HTTPException(422, {"code": "unknown_role", "message": "Select a role from the canonical role catalog"})


def _validate_department(db: Session, department: str) -> None:
    if department not in get_departments(db):
        raise HTTPException(422, {"code": "unknown_department", "message": "Select a configured department"})


def _save_departments(db: Session, values: list[str]) -> None:
    row = db.query(SystemSetting).filter(SystemSetting.key == "departments_json").first()
    encoded = json.dumps(values, ensure_ascii=False)
    if row:
        row.value = encoded
    else:
        db.add(SystemSetting(key="departments_json", value=encoded))
    invalidate_settings_cache()


def _serialize(user: User, profile: UserIdentityProfile | None) -> dict:
    profile = profile or UserIdentityProfile(user_id=user.id)
    return {"id": user.id, "username": user.username, "role": user.role, "department": user.department,
            "is_active": bool(user.is_active), "created_at": user.created_at, "full_name": profile.full_name,
            "employee_id": profile.employee_id, "position": profile.position, "phone": profile.phone,
            "email": profile.email, "telegram": profile.telegram, "avatar_url": profile.avatar_url,
            "last_login_at": profile.last_login_at}


@router.get("/users")
def list_users(page: int = Query(1, ge=1), page_size: int = Query(25, ge=10, le=100), search: str = "", department: str = "", role: str = "", status: str = "", sort_by: str = "created_at", sort_direction: str = "desc", db: Session = Depends(get_db), _: User = Depends(require_identity("platform_admin_view"))):
    query = db.query(User, UserIdentityProfile).outerjoin(UserIdentityProfile, UserIdentityProfile.user_id == User.id)
    if search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(User.username.ilike(term), UserIdentityProfile.full_name.ilike(term), UserIdentityProfile.email.ilike(term), UserIdentityProfile.employee_id.ilike(term)))
    if department: query = query.filter(User.department == department)
    if role: query = query.filter(User.role == role)
    if status in {"active", "inactive"}: query = query.filter(User.is_active.is_(status == "active"))
    total = query.count()
    fields = {"username": User.username, "department": User.department, "role": User.role, "created_at": User.created_at, "full_name": UserIdentityProfile.full_name, "last_login": UserIdentityProfile.last_login_at}
    sort_column = fields.get(sort_by, User.created_at)
    query = query.order_by(sort_column.asc() if sort_direction == "asc" else sort_column.desc())
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_serialize(user, profile) for user, profile in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/users")
def create_user(data: UserIdentityPayload, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_identity("platform_admin_manage"))):
    if db.query(User).filter(User.username == data.username).first(): raise HTTPException(400, "Username already exists")
    if not data.password: raise HTTPException(400, "Password is required")
    _validate_role(db, data.role); _validate_department(db, data.department)
    user = User(username=data.username, password_hash=hash_password(data.password), role=data.role, department=data.department, is_active=data.is_active)
    db.add(user); db.flush()
    profile = _profile(db, user.id)
    for key in ("full_name", "employee_id", "position", "phone", "email", "telegram", "avatar_url"): setattr(profile, key, getattr(data, key))
    _record(db, user.id, "created", admin.username, "Enterprise identity created")
    append_audit(db, actor=admin.username, action="user.create", entity_type="user", entity_id=user.id, details={"username": user.username, "role": user.role, "department": user.department, "is_active": user.is_active}, **_audit_context(request))
    db.commit(); db.refresh(user)
    return _serialize(user, profile)


@router.put("/users/{user_id}")
def update_user(user_id: int, data: UserIdentityPayload, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_identity("platform_admin_manage"))):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    if admin.id == user_id and (not data.is_active or data.role not in {"admin", "super_admin"}):
        raise HTTPException(409, {"code": "self_lockout", "message": "You cannot remove your own administrator access"})
    duplicate = db.query(User).filter(User.username == data.username, User.id != user_id).first()
    if duplicate: raise HTTPException(400, "Username already exists")
    _validate_role(db, data.role); _validate_department(db, data.department)
    before = {"username": user.username, "role": user.role, "department": user.department, "is_active": bool(user.is_active)}
    for key in ("username", "role", "department", "is_active"): setattr(user, key, getattr(data, key))
    if data.password: user.password_hash = hash_password(data.password); user.password = None
    profile = _profile(db, user_id)
    for key in ("full_name", "employee_id", "position", "phone", "email", "telegram", "avatar_url"): setattr(profile, key, getattr(data, key))
    _record(db, user_id, "updated", admin.username, "Enterprise identity updated")
    append_audit(db, actor=admin.username, action="user.update", entity_type="user", entity_id=user_id, details={"before": before, "after": {"username": user.username, "role": user.role, "department": user.department, "is_active": bool(user.is_active)}, "password_changed": bool(data.password)}, **_audit_context(request))
    db.commit(); return _serialize(user, profile)


@router.post("/users/{user_id}/status")
def set_status(user_id: int, active: bool, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_identity("platform_admin_manage"))):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    if admin.id == user_id and not active:
        raise HTTPException(409, {"code": "self_lockout", "message": "You cannot deactivate your own account"})
    user.is_active = active; _record(db, user_id, "activated" if active else "deactivated", admin.username)
    append_audit(db, actor=admin.username, action="user.activate" if active else "user.deactivate", entity_type="user", entity_id=user_id, details={"username": user.username}, **_audit_context(request))
    db.commit(); return {"id": user_id, "is_active": active}


@router.post("/users/{user_id}/temporary-password")
def temporary_password(user_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_identity("platform_admin_security"))):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    password = secrets.token_urlsafe(9)
    user.password_hash = hash_password(password); user.password = None; _record(db, user_id, "temporary_password", admin.username)
    append_audit(db, actor=admin.username, action="user.temporary_password", entity_type="user", entity_id=user_id, details={"username": user.username}, **_audit_context(request))
    db.commit(); return {"temporary_password": password}


@router.post("/users/{user_id}/force-logout")
def force_logout(user_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_identity("platform_admin_security"))):
    db.query(UserIdentitySession).filter(UserIdentitySession.user_id == user_id).update({"is_active": False})
    _record(db, user_id, "force_logout", admin.username, "Tracked sessions revoked")
    append_audit(db, actor=admin.username, action="user.force_logout", entity_type="user", entity_id=user_id, **_audit_context(request))
    db.commit(); return {"message": "Tracked sessions revoked"}


@router.get("/users/{user_id}/activity")
def user_activity(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_identity("platform_admin_view"))):
    return db.query(UserIdentityActivity).filter(UserIdentityActivity.user_id == user_id).order_by(UserIdentityActivity.created_at.desc()).limit(100).all()


@router.get("/meta")
def identity_meta(db: Session = Depends(get_db), _: User = Depends(require_identity("platform_admin_view"))):
    departments = get_departments(db)
    roles = db.query(Role).order_by(Role.sort_order, Role.id).all()
    active = get_versioned_setting(db, "platform.roles.active", {})
    security = get_versioned_setting(db, "platform.security", {"minimum_password_length": 8, "login_attempt_limit": 5, "lockout_minutes": 15, "session_expiration_minutes": 60, "require_password_change": False})
    return {"departments": departments, "roles": [role.role_key for role in roles if active.get(role.role_key, True)], "role_options": [{"key": role.role_key, "label": role.label, "is_active": active.get(role.role_key, True)} for role in roles], "password_policy": security}


@router.get("/departments")
def list_departments(db: Session = Depends(get_db), _: User = Depends(require_identity("platform_admin_view"))):
    counts = dict(db.query(User.department, func.count(User.id)).group_by(User.department).all())
    return {"items": [{"name": name, "user_count": counts.get(name, 0), "is_system": name == "Admin"} for name in get_departments(db)]}


@router.post("/departments")
def create_department(data: DepartmentPayload, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_identity("platform_admin_manage"))):
    name = data.name.strip()
    current = get_departments(db)
    if any(value.casefold() == name.casefold() for value in current):
        raise HTTPException(409, {"code": "department_exists", "message": "Department already exists"})
    _save_departments(db, [*current, name])
    append_audit(db, actor=admin.username, action="department.create", entity_type="department", details={"name": name}, **_audit_context(request))
    db.commit(); return {"name": name, "user_count": 0, "is_system": False}


@router.put("/departments/{department_name}")
def rename_department(department_name: str, data: DepartmentPayload, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_identity("platform_admin_manage"))):
    current = get_departments(db)
    if department_name not in current: raise HTTPException(404, "Department not found")
    if department_name == "Admin": raise HTTPException(409, {"code": "system_department", "message": "The recovery department cannot be renamed"})
    name = data.name.strip()
    if any(value.casefold() == name.casefold() and value != department_name for value in current):
        raise HTTPException(409, {"code": "department_exists", "message": "Department already exists"})
    db.query(User).filter(User.department == department_name).update({"department": name}, synchronize_session=False)
    _save_departments(db, [name if value == department_name else value for value in current])
    append_audit(db, actor=admin.username, action="department.rename", entity_type="department", details={"from": department_name, "to": name}, **_audit_context(request))
    db.commit(); return {"name": name}


@router.delete("/departments/{department_name}")
def delete_department(department_name: str, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_identity("platform_admin_manage"))):
    current = get_departments(db)
    if department_name not in current: raise HTTPException(404, "Department not found")
    if department_name == "Admin": raise HTTPException(409, {"code": "system_department", "message": "The recovery department cannot be removed"})
    count = db.query(User).filter(User.department == department_name).count()
    if count: raise HTTPException(409, {"code": "department_in_use", "message": "Reassign department users before removing it", "count": count})
    _save_departments(db, [value for value in current if value != department_name])
    append_audit(db, actor=admin.username, action="department.delete", entity_type="department", details={"name": department_name}, **_audit_context(request))
    db.commit(); return {"status": "deleted"}


@router.get("/activity")
def activity(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), _: User = Depends(require_identity("platform_admin_audit"))):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).all()
    return {"items": [{"id": row.id, "actor": row.username, "action": row.action, "entity_type": row.entity_type, "entity_id": row.entity_id, "created_at": row.created_at} for row in rows]}


@router.get("/sessions")
def sessions(db: Session = Depends(get_db), _: User = Depends(require_identity("platform_admin_security"))):
    rows = db.query(UserIdentitySession, User.username).join(User, User.id == UserIdentitySession.user_id).order_by(UserIdentitySession.last_seen_at.desc()).limit(500).all()
    return {"items": [{"id": session.id, "user_id": session.user_id, "username": username, "device": session.device, "browser": session.browser, "ip_address": session.ip_address, "location": session.location, "is_active": bool(session.is_active), "last_seen_at": session.last_seen_at, "created_at": session.created_at} for session, username in rows]}


@router.post("/sessions/{session_id}/revoke")
def revoke_session(session_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_identity("platform_admin_security"))):
    session = db.get(UserIdentitySession, session_id)
    if not session: raise HTTPException(404, "Session not found")
    if not session.is_active: return {"status": "already_revoked"}
    session.is_active = False
    append_audit(db, actor=admin.username, action="session.revoke", entity_type="user_session", entity_id=session.id, details={"user_id": session.user_id}, **_audit_context(request))
    db.commit(); return {"status": "revoked"}
