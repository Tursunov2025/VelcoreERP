import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from auth.deps import require_admin
from auth.security import hash_password
from database import get_db
from models import User, UserIdentityActivity, UserIdentityProfile, UserIdentitySession

router = APIRouter(prefix="/admin/identity", tags=["enterprise identity"])


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


def _profile(db: Session, user_id: int) -> UserIdentityProfile:
    profile = db.query(UserIdentityProfile).filter(UserIdentityProfile.user_id == user_id).first()
    if not profile:
        profile = UserIdentityProfile(user_id=user_id)
        db.add(profile)
        db.flush()
    return profile


def _record(db: Session, user_id: int, action: str, actor: str, details: str = ""):
    db.add(UserIdentityActivity(user_id=user_id, action=action, actor_username=actor, details=details))


def _serialize(user: User, profile: UserIdentityProfile | None) -> dict:
    profile = profile or UserIdentityProfile(user_id=user.id)
    return {"id": user.id, "username": user.username, "role": user.role, "department": user.department,
            "is_active": bool(user.is_active), "created_at": user.created_at, "full_name": profile.full_name,
            "employee_id": profile.employee_id, "position": profile.position, "phone": profile.phone,
            "email": profile.email, "telegram": profile.telegram, "avatar_url": profile.avatar_url,
            "last_login_at": profile.last_login_at}


@router.get("/users")
def list_users(page: int = Query(1, ge=1), page_size: int = Query(25, ge=10, le=100), search: str = "", department: str = "", role: str = "", status: str = "", sort_by: str = "created_at", sort_direction: str = "desc", db: Session = Depends(get_db), _: User = Depends(require_admin)):
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
def create_user(data: UserIdentityPayload, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if db.query(User).filter(User.username == data.username).first(): raise HTTPException(400, "Username already exists")
    if not data.password: raise HTTPException(400, "Password is required")
    user = User(username=data.username, password_hash=hash_password(data.password), role=data.role, department=data.department, is_active=data.is_active)
    db.add(user); db.flush()
    profile = _profile(db, user.id)
    for key in ("full_name", "employee_id", "position", "phone", "email", "telegram", "avatar_url"): setattr(profile, key, getattr(data, key))
    _record(db, user.id, "created", admin.username, "Enterprise identity created")
    db.commit(); db.refresh(user)
    return _serialize(user, profile)


@router.put("/users/{user_id}")
def update_user(user_id: int, data: UserIdentityPayload, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    duplicate = db.query(User).filter(User.username == data.username, User.id != user_id).first()
    if duplicate: raise HTTPException(400, "Username already exists")
    for key in ("username", "role", "department", "is_active"): setattr(user, key, getattr(data, key))
    if data.password: user.password_hash = hash_password(data.password); user.password = None
    profile = _profile(db, user_id)
    for key in ("full_name", "employee_id", "position", "phone", "email", "telegram", "avatar_url"): setattr(profile, key, getattr(data, key))
    _record(db, user_id, "updated", admin.username, "Enterprise identity updated")
    db.commit(); return _serialize(user, profile)


@router.post("/users/{user_id}/status")
def set_status(user_id: int, active: bool, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    user.is_active = active; _record(db, user_id, "activated" if active else "deactivated", admin.username)
    db.commit(); return {"id": user_id, "is_active": active}


@router.post("/users/{user_id}/temporary-password")
def temporary_password(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    password = secrets.token_urlsafe(9)
    user.password_hash = hash_password(password); user.password = None; _record(db, user_id, "temporary_password", admin.username)
    db.commit(); return {"temporary_password": password}


@router.post("/users/{user_id}/force-logout")
def force_logout(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    db.query(UserIdentitySession).filter(UserIdentitySession.user_id == user_id).update({"is_active": False})
    _record(db, user_id, "force_logout", admin.username, "Tracked sessions revoked")
    db.commit(); return {"message": "Tracked sessions revoked"}


@router.get("/users/{user_id}/activity")
def user_activity(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(UserIdentityActivity).filter(UserIdentityActivity.user_id == user_id).order_by(UserIdentityActivity.created_at.desc()).limit(100).all()


@router.get("/meta")
def identity_meta(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    departments = [row[0] for row in db.query(User.department).distinct().order_by(User.department).all() if row[0]]
    roles = [row[0] for row in db.query(User.role).distinct().order_by(User.role).all() if row[0]]
    return {"departments": departments, "roles": roles, "password_policy": {"minimum_length": 8, "uppercase": False, "lowercase": False, "numbers": False, "special_characters": False, "expiration_days": 0, "history_count": 0, "failed_login_lock": 0, "two_factor_ready": True}}
