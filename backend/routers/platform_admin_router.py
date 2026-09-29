"""Authenticated, permission-enforced Platform Administration APIs."""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from config.paths import BACKUP_PATH, DATABASE_URL, DB_PATH, UPLOAD_PATH
from config.production import parse_cors_origins
from constants import ALL_PERMISSION_KEYS
from database import get_db
from models import AuditLog, ModuleSetting, NavigationItem, PermissionDefinition, Role, RolePermission, SystemSetting, User, UserIdentitySession
from services.branding import DEFAULT_BRANDING, get_branding, reset_branding, update_branding
from services.permissions import user_has_permission
from services.platform_administration import append_audit, get_versioned_setting, put_versioned_setting, redact, sha256_file
from services.super_admin_service import DEFAULT_NAV, get_navigation_tree, invalidate_super_admin_cache, seed_super_admin_defaults
from services.settings_store import get_settings_for_admin
from services.telegram import send_test_message

router = APIRouter(prefix="/admin/platform", tags=["platform-administration"])

ICON_ALLOWLIST = {"dashboard", "orders", "production", "warehouse", "settings", "users", "security", "modules", "integration", "backup", "audit", "system", "about", "displayCenter", "mes", "materials", "finance", "crm", "logistics"}
CORE_MODULES = {"authentication", "platform_administration"}
MODULE_DEPENDENCIES = {"finance": ["crm"], "logistics": ["warehouse"], "technology": ["production"]}
MODULE_ROUTES = {
    "authentication": ["/login"], "platform_administration": ["/admin"], "orders": ["/orders"],
    "crm": ["/crm", "/orders"], "warehouse": ["/warehouse"], "production": ["/production"],
    "technology": ["/mes/templates"], "logistics": ["/logistics"], "finance": ["/finance", "/invoices"],
    "llp": ["/logistics/llp"], "gps": ["/logistics/gps"], "driver": ["/driver"], "qc": ["/mes/terminal/qc"],
    "mes": ["/mes"], "materials": ["/materials"], "chat": ["/chat"], "tasks": ["/tasks"],
    "display_center": ["/display-center"], "analytics": ["/analytics"],
}


def _allowed(db: Session, user: User, permission: str) -> bool:
    return user.role == "super_admin" or user_has_permission(db, user, permission)


def require_platform(permission: str):
    def dependency(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> User:
        if not _allowed(db, user, permission):
            raise HTTPException(403, f"Permission required: {permission}")
        return user
    return dependency


def _audit_context(request: Request) -> dict[str, str]:
    return {"ip_address": request.client.host if request.client else "", "correlation_id": request.headers.get("x-request-id", "")[:128]}


class VersionedPayload(BaseModel):
    version: int = Field(ge=0)


class RoleCreate(BaseModel):
    role_key: str = Field(pattern=r"^[a-z][a-z0-9_]{2,49}$")
    label: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)
    permissions: dict[str, bool] = Field(default_factory=dict)


class RoleUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    permissions: dict[str, bool] | None = None


class NavigationUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    icon: str = "dashboard"
    visible: bool = True
    sort_order: int = Field(ge=0, le=10000)
    permissions: list[str] = Field(default_factory=list)

    @field_validator("icon")
    @classmethod
    def icon_allowed(cls, value: str) -> str:
        if value not in ICON_ALLOWLIST:
            raise ValueError("Icon is not in the allowlist")
        return value


class ModuleUpdate(BaseModel):
    state: Literal["enabled", "disabled", "maintenance"]
    version: int = Field(ge=0)


class AppearanceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_name: str = Field(min_length=1, max_length=100)
    short_name: str = Field(default="Velcore", max_length=30)
    color_primary: str = "#000000"
    color_secondary: str = "#ffffff"
    color_background: str = "#f5f6fa"
    color_sidebar: str = "#000000"
    color_button: str = "#000000"
    color_button_text: str = "#ffffff"
    color_secondary_button: str = "#ffffff"
    color_secondary_button_text: str = "#111827"
    color_card: str = "#ffffff"
    color_sidebar_text: str = "#ffffff"
    color_sidebar_active: str = "#ffffff"
    color_sidebar_active_text: str = "#111827"
    color_header: str = "#ffffff"
    color_heading: str = "#111827"
    color_text: str = "#111827"
    color_muted: str = "#6b7280"
    color_link: str = "#2563eb"
    color_input_background: str = "#ffffff"
    color_input_text: str = "#111827"
    color_input_border: str = "#d1d5db"
    color_table_header: str = "#f8fafc"
    color_table_header_text: str = "#475569"
    color_table_row: str = "#ffffff"
    color_border: str = "#e5e7eb"
    color_success: str = "#22c55e"
    color_warning: str = "#f59e0b"
    color_danger: str = "#ef4444"
    color_info: str = "#3b82f6"
    color_focus: str = "#2563eb"
    theme_mode: Literal["light", "dark", "system"] = "system"
    interface_density: Literal["comfortable", "compact"] = "comfortable"
    button_radius: int = Field(default=16, ge=0, le=40)
    font_scale: float = Field(default=1, ge=0.875, le=1.25)
    reduced_motion: bool = False
    login_footer: str = Field(default="", max_length=250)
    version: int = Field(ge=0)

    @field_validator(*[field for field in DEFAULT_BRANDING if field.startswith("color_")])
    @classmethod
    def valid_color(cls, value: str) -> str:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("Expected a six-digit hex color")
        return value.lower()

    @model_validator(mode="after")
    def accessible_contrast(self):
        def luminance(value: str) -> float:
            channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
            return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]
        def ratio(a: str, b: str) -> float:
            high, low = sorted((luminance(a), luminance(b)), reverse=True)
            return (high + .05) / (low + .05)
        pairs = {
            "button_text/button": (self.color_button_text, self.color_button),
            "secondary_button_text/secondary_button": (self.color_secondary_button_text, self.color_secondary_button),
            "sidebar_text/sidebar": (self.color_sidebar_text, self.color_sidebar),
            "sidebar_active_text/sidebar_active": (self.color_sidebar_active_text, self.color_sidebar_active),
            "heading/background": (self.color_heading, self.color_background),
            "text/background": (self.color_text, self.color_background),
            "input_text/input_background": (self.color_input_text, self.color_input_background),
            "table_header_text/table_header": (self.color_table_header_text, self.color_table_header),
        }
        failures = [{"pair": name, "ratio": round(ratio(*colors), 2), "minimum": 4.5} for name, colors in pairs.items() if ratio(*colors) < 4.5]
        if failures:
            raise ValueError(json.dumps({"code": "appearance_contrast_failed", "failures": failures}))
        return self


SECURITY_DEFAULTS = {
    "minimum_password_length": 8, "login_attempt_limit": 5, "lockout_minutes": 15,
    "session_expiration_minutes": 60, "require_password_change": False,
    "allowed_cors_origins": [], "secure_cookie_required": True,
}


class SecurityUpdate(VersionedPayload):
    minimum_password_length: int = Field(ge=8, le=128)
    login_attempt_limit: int = Field(ge=3, le=20)
    lockout_minutes: int = Field(ge=1, le=1440)
    session_expiration_minutes: int = Field(ge=5, le=43200)
    require_password_change: bool = False
    allowed_cors_origins: list[str] = Field(default_factory=list, max_length=50)
    secure_cookie_required: bool = True
    confirmation: str

    @field_validator("allowed_cors_origins")
    @classmethod
    def origins_valid(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(r"https?://[A-Za-z0-9.-]+(?::\d+)?", value):
                raise ValueError(f"Invalid CORS origin: {value}")
        return list(dict.fromkeys(value.rstrip("/") for value in values))


@router.get("/access")
def access(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    permissions = [key for key in ALL_PERMISSION_KEYS if key.startswith("platform_admin_") and _allowed(db, user, key)]
    if "platform_admin_view" not in permissions and not _allowed(db, user, "platform_admin_manage"):
        raise HTTPException(403, "Platform Administration access required")
    return {"permissions": permissions, "is_owner": user.role == "super_admin"}


def _role_active_map(db: Session) -> dict[str, bool]:
    return get_versioned_setting(db, "platform.roles.active", {})


@router.get("/roles")
def list_roles(db: Session = Depends(get_db), _: User = Depends(require_platform("platform_admin_view"))):
    seed_super_admin_defaults(db)
    active = _role_active_map(db)
    counts = dict(db.query(User.role, func.count(User.id)).group_by(User.role).all())
    definitions = db.query(PermissionDefinition).order_by(PermissionDefinition.module, PermissionDefinition.perm_key).all()
    roles = []
    for role in db.query(Role).order_by(Role.sort_order, Role.id).all():
        inherited = role.role_key == "super_admin"
        persisted = {row.permission_key: bool(row.enabled) for row in role.permissions}
        permissions = {key: True for key in ALL_PERMISSION_KEYS} if inherited else {
            key: bool(persisted.get(key, False)) for key in ALL_PERMISSION_KEYS
        }
        roles.append({"id": role.id, "role_key": role.role_key, "label": role.label, "description": role.description, "is_system": role.is_system, "is_active": active.get(role.role_key, True), "user_count": counts.get(role.role_key, 0), "permissions": permissions, "permissions_inherited": inherited})
    assigned = {
        key: [role.role_key for role in db.query(Role).all() if any(row.permission_key == key and row.enabled for row in role.permissions)]
        for key in ALL_PERMISSION_KEYS
    }
    return {"roles": roles, "permission_groups": [{"key": row.perm_key, "label": row.label, "module": row.module, "description": row.description, "roles_assigned": assigned.get(row.perm_key, [])} for row in definitions]}


@router.post("/roles")
def create_role(payload: RoleCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_platform("platform_admin_roles"))):
    if db.query(Role).filter(Role.role_key == payload.role_key).first():
        raise HTTPException(409, "Role key already exists")
    invalid = set(payload.permissions) - set(ALL_PERMISSION_KEYS)
    if invalid: raise HTTPException(422, f"Unknown permissions: {', '.join(sorted(invalid))}")
    role = Role(role_key=payload.role_key, label=payload.label.strip(), description=payload.description.strip(), is_system=False, sort_order=100)
    db.add(role); db.flush()
    for key, enabled in payload.permissions.items(): db.add(RolePermission(role_id=role.id, permission_key=key, enabled=enabled))
    append_audit(db, actor=user.username, action="role.create", entity_type="role", entity_id=role.id, details={"role_key": role.role_key, "permissions": payload.permissions}, **_audit_context(request))
    db.commit(); return {"id": role.id}


@router.put("/roles/{role_id}")
def update_role(role_id: int, payload: RoleUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_platform("platform_admin_roles"))):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role: raise HTTPException(404, "Role not found")
    if role.role_key == "super_admin" and (payload.is_active is False or payload.permissions is not None):
        raise HTTPException(409, {"code": "root_role_protected", "message": "The built-in platform owner role uses inherited system permissions"})
    if user.role == role.role_key and (
        payload.is_active is False
        or payload.permissions is not None
        and (not payload.permissions.get("platform_admin_view", False) or not payload.permissions.get("platform_admin_roles", False))
    ):
        raise HTTPException(409, "You cannot remove your own role-based Platform Administration access")
    if payload.label is not None: role.label = payload.label.strip()
    if payload.description is not None: role.description = payload.description.strip()
    if payload.permissions is not None:
        invalid = set(payload.permissions) - set(ALL_PERMISSION_KEYS)
        if invalid: raise HTTPException(422, f"Unknown permissions: {', '.join(sorted(invalid))}")
        replacement = {key: bool(payload.permissions.get(key, False)) for key in ALL_PERMISSION_KEYS}
        existing = {row.permission_key: row for row in db.query(RolePermission).filter(RolePermission.role_id == role.id).all()}
        changes = {}
        for key, enabled in replacement.items():
            previous = bool(existing[key].enabled) if key in existing else False
            if previous != enabled: changes[key] = {"from": previous, "to": enabled}
            if key in existing: existing[key].enabled = enabled
            else: db.add(RolePermission(role_id=role.id, permission_key=key, enabled=enabled))
        payload_details = payload.model_dump(exclude_none=True)
        payload_details["permission_changes"] = changes
        payload_details.pop("permissions", None)
    else:
        payload_details = payload.model_dump(exclude_none=True)
    if payload.is_active is not None:
        states = _role_active_map(db); version = states.pop("version", 0); states[role.role_key] = payload.is_active
        put_versioned_setting(db, "platform.roles.active", states, version)
    append_audit(db, actor=user.username, action="role.update", entity_type="role", entity_id=role.id, details=payload_details, **_audit_context(request))
    db.commit(); return {"status": "updated"}


@router.delete("/roles/{role_id}")
def delete_role(role_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_platform("platform_admin_roles"))):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role: raise HTTPException(404, "Role not found")
    if role.is_system: raise HTTPException(409, "Built-in roles cannot be deleted")
    count = db.query(User).filter(User.role == role.role_key).count()
    if count: raise HTTPException(409, f"Role is assigned to {count} user(s); reassign them first")
    append_audit(db, actor=user.username, action="role.delete", entity_type="role", entity_id=role.id, details={"role_key": role.role_key}, **_audit_context(request))
    db.delete(role); db.commit(); return {"status": "deleted"}


@router.get("/appearance")
def appearance(db: Session = Depends(get_db), _: User = Depends(require_platform("platform_admin_view"))):
    extra = get_versioned_setting(db, "platform.appearance", {"short_name": "Velcore", "interface_density": "comfortable", "login_footer": ""})
    return {**get_branding(db), **extra}


@router.put("/appearance")
def save_appearance(payload: AppearanceUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_platform("platform_admin_manage"))):
    try:
        extra = put_versioned_setting(db, "platform.appearance", {"short_name": payload.short_name, "interface_density": payload.interface_density, "login_footer": payload.login_footer}, payload.version)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    branding_payload = {
        key: value for key, value in payload.model_dump().items()
        if key in DEFAULT_BRANDING
    }
    result = update_branding(db, branding_payload)
    append_audit(db, actor=user.username, action="appearance.update", entity_type="appearance", details=payload.model_dump(), **_audit_context(request)); db.commit()
    return {**result, **extra}


@router.post("/appearance/reset")
def restore_appearance(request: Request, db: Session = Depends(get_db), user: User = Depends(require_platform("platform_admin_manage"))):
    result = reset_branding(db); row = db.query(SystemSetting).filter(SystemSetting.key == "platform.appearance").first()
    if row: db.delete(row)
    append_audit(db, actor=user.username, action="appearance.reset", entity_type="appearance", **_audit_context(request)); db.commit()
    return {**result, "short_name": "Velcore", "interface_density": "comfortable", "login_footer": "", "version": 0}


@router.post("/appearance/logo")
async def upload_logo(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_platform("platform_admin_manage"))):
    allowed = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
    if file.content_type not in allowed: raise HTTPException(415, "Only PNG, JPEG, and WebP images are allowed")
    content = await file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024: raise HTTPException(413, "Logo must not exceed 2 MB")
    signatures = content.startswith(b"\x89PNG\r\n\x1a\n") or content.startswith(b"\xff\xd8\xff") or content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    if not signatures: raise HTTPException(415, "Uploaded content is not a valid supported image")
    directory = UPLOAD_PATH / "branding"; directory.mkdir(parents=True, exist_ok=True)
    name = f"platform_logo_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}{allowed[file.content_type]}"; path = directory / name; path.write_bytes(content)
    url = f"/uploads/branding/{name}"; update_branding(db, {"logo_main": url, "logo_sidebar": url})
    append_audit(db, actor=user.username, action="appearance.logo_upload", entity_type="appearance", details={"content_type": file.content_type, "size": len(content)}, **_audit_context(request)); db.commit()
    return {"url": url}


@router.delete("/appearance/logo")
def remove_logo(request: Request, db: Session = Depends(get_db), user: User = Depends(require_platform("platform_admin_manage"))):
    result = update_branding(db, {"logo_main": "", "logo_sidebar": ""}); append_audit(db, actor=user.username, action="appearance.logo_remove", entity_type="appearance", **_audit_context(request)); db.commit(); return result


@router.get("/navigation")
def navigation(db: Session = Depends(get_db), _: User = Depends(require_platform("platform_admin_view"))):
    seed_super_admin_defaults(db); return {"items": get_navigation_tree(db), "icon_allowlist": sorted(ICON_ALLOWLIST)}


@router.put("/navigation/{item_id}")
def save_navigation(item_id: int, payload: NavigationUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_platform("platform_admin_manage"))):
    item = db.query(NavigationItem).filter(NavigationItem.id == item_id).first()
    if not item: raise HTTPException(404, "Navigation item not found")
    if item.path == "/admin" and not payload.visible: raise HTTPException(409, "Platform Administration recovery navigation cannot be hidden")
    invalid = set(payload.permissions) - set(ALL_PERMISSION_KEYS)
    if invalid: raise HTTPException(422, "Unknown navigation permission")
    item.label = payload.label.strip(); item.icon = payload.icon; item.visible = payload.visible; item.hidden = not payload.visible; item.sort_order = payload.sort_order; item.permissions_json = json.dumps(payload.permissions)
    append_audit(db, actor=user.username, action="navigation.update", entity_type="navigation_item", entity_id=item.id, details=payload.model_dump(), **_audit_context(request)); db.commit(); invalidate_super_admin_cache(); return {"status": "updated"}


@router.post("/navigation/reset")
def reset_navigation(request: Request, db: Session = Depends(get_db), user: User = Depends(require_platform("platform_admin_manage"))):
    defaults = {row[0]: row for row in DEFAULT_NAV}
    for item in db.query(NavigationItem).all():
        if item.nav_key in defaults:
            row = defaults[item.nav_key]; item.label = row[1]; item.path = row[3]; item.sort_order = row[5]; item.visible = True; item.hidden = False
    append_audit(db, actor=user.username, action="navigation.reset", entity_type="navigation", **_audit_context(request)); db.commit(); invalidate_super_admin_cache(); return {"status": "restored"}


def _module_states(db: Session) -> dict[str, Any]:
    return get_versioned_setting(db, "platform.modules.states", {})


@router.get("/modules")
def modules(db: Session = Depends(get_db), _: User = Depends(require_platform("platform_admin_view"))):
    seed_super_admin_defaults(db); states = _module_states(db)
    items = [{"id": row.id, "module_key": row.module_key, "label": row.label, "state": states.get(row.module_key, "enabled" if row.enabled else "disabled"), "routes": MODULE_ROUTES.get(row.module_key, [row.url]), "dependencies": MODULE_DEPENDENCIES.get(row.module_key, []), "required": row.module_key in CORE_MODULES} for row in db.query(ModuleSetting).order_by(ModuleSetting.sort_order).all()]
    return {"items": items, "version": states["version"]}


@router.put("/modules/{module_key}")
def save_module(module_key: str, payload: ModuleUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_platform("platform_admin_manage"))):
    module = db.query(ModuleSetting).filter(ModuleSetting.module_key == module_key).first()
    if not module: raise HTTPException(404, "Module not found")
    if module_key in CORE_MODULES and payload.state != "enabled": raise HTTPException(409, "Core modules cannot be disabled")
    if payload.state == "disabled":
        states = _module_states(db)
        dependents = [key for key, dependencies in MODULE_DEPENDENCIES.items() if module_key in dependencies and states.get(key, "enabled") != "disabled"]
        if dependents: raise HTTPException(409, f"Disable dependent modules first: {', '.join(dependents)}")
    states = _module_states(db); version = states.pop("version"); states[module_key] = payload.state
    result = put_versioned_setting(db, "platform.modules.states", states, payload.version); module.enabled = payload.state != "disabled"
    runtime_row = db.query(SystemSetting).filter(SystemSetting.key == "platform_module_states_runtime").first()
    runtime_value = json.dumps({key: value for key, value in result.items() if key != "version"})
    if runtime_row: runtime_row.value = runtime_value
    else: db.add(SystemSetting(key="platform_module_states_runtime", value=runtime_value))
    append_audit(db, actor=user.username, action="module.state", entity_type="module", details={"module_key": module_key, "state": payload.state}, **_audit_context(request)); db.commit(); invalidate_super_admin_cache(); return {"module_key": module_key, "state": payload.state, "version": result["version"]}


@router.get("/integrations")
def integrations(db: Session = Depends(get_db), _: User = Depends(require_platform("platform_admin_view"))):
    telegram = get_versioned_setting(db, "platform.integration.telegram", {"enabled": False, "last_success": None, "last_error": None})
    configured = bool(get_settings_for_admin(db).get("telegram_bot_token") or os.getenv("TELEGRAM_BOT_TOKEN", "").strip())
    return {"items": [
        {"key": "telegram", "label": "Telegram", "implemented": True, "configured": configured, "enabled": telegram.get("enabled", False), "last_success": telegram.get("last_success"), "last_error": telegram.get("last_error"), "secret": "********" if configured else ""},
        {"key": "whatsapp", "label": "WhatsApp", "implemented": False, "configured": False, "enabled": False, "status": "Not implemented"},
    ]}


@router.post("/integrations/telegram/test")
async def test_telegram_integration(request: Request, db: Session = Depends(get_db), user: User = Depends(require_platform("platform_admin_manage"))):
    result = await send_test_message(db)
    current = get_versioned_setting(db, "platform.integration.telegram", {"enabled": True, "last_success": None, "last_error": None})
    version = current.pop("version")
    current["last_success"] = datetime.utcnow().isoformat() if result.get("ok") else current.get("last_success")
    current["last_error"] = None if result.get("ok") else str(result.get("error") or "Connection test failed")[:500]
    put_versioned_setting(db, "platform.integration.telegram", current, version)
    append_audit(db, actor=user.username, action="integration.test", entity_type="integration", details={"integration": "telegram", "result": "success" if result.get("ok") else "failure"}, result="success" if result.get("ok") else "failure", **_audit_context(request)); db.commit()
    if not result.get("ok"): raise HTTPException(400, current["last_error"])
    return {"ok": True, "checked_at": current["last_success"]}


@router.get("/backups")
def backups(db: Session = Depends(get_db), _: User = Depends(require_platform("platform_admin_backup"))):
    directory = BACKUP_PATH / "platform"; directory.mkdir(parents=True, exist_ok=True); items = []
    for path in sorted(directory.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
        valid = False
        try:
            connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True); valid = connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"; connection.close()
        except sqlite3.Error: pass
        items.append({"name": path.name, "created_at": datetime.utcfromtimestamp(path.stat().st_mtime).isoformat(), "size": path.stat().st_size, "source": "primary database", "valid": valid, "sha256": sha256_file(path)})
    return {"database": {"engine": "sqlite" if DATABASE_URL.startswith("sqlite") else "postgresql", "status": "connected"}, "items": items, "restore_mode": "offline_only"}


@router.post("/backups")
def create_backup(request: Request, db: Session = Depends(get_db), user: User = Depends(require_platform("platform_admin_backup"))):
    if not DATABASE_URL.startswith("sqlite"): raise HTTPException(501, "Online PostgreSQL backup is not implemented; use the documented database-native workflow")
    directory = BACKUP_PATH / "platform"; directory.mkdir(parents=True, exist_ok=True); destination = directory / f"velcore_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}.db"
    source = sqlite3.connect(str(DB_PATH)); target = sqlite3.connect(str(destination))
    try: source.backup(target)
    finally: target.close(); source.close()
    check = sqlite3.connect(f"file:{destination.as_posix()}?mode=ro", uri=True); valid = check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"; check.close()
    if not valid: destination.unlink(missing_ok=True); raise HTTPException(500, "Backup validation failed")
    append_audit(db, actor=user.username, action="backup.create", entity_type="backup", details={"name": destination.name, "size": destination.stat().st_size, "sha256": sha256_file(destination)}, **_audit_context(request)); db.commit()
    return {"name": destination.name, "valid": True, "size": destination.stat().st_size, "sha256": sha256_file(destination)}


def _safe_backup(name: str) -> Path:
    if not re.fullmatch(r"velcore_[0-9_]+\.db", name): raise HTTPException(400, "Invalid backup name")
    path = (BACKUP_PATH / "platform" / name).resolve(); root = (BACKUP_PATH / "platform").resolve()
    if path.parent != root or not path.is_file(): raise HTTPException(404, "Backup not found")
    return path


@router.get("/backups/{name}/download")
def download_backup(name: str, request: Request, db: Session = Depends(get_db), user: User = Depends(require_platform("platform_admin_backup"))):
    path = _safe_backup(name); append_audit(db, actor=user.username, action="backup.download", entity_type="backup", details={"name": path.name}, **_audit_context(request)); db.commit(); return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@router.post("/backups/{name}/preflight")
def backup_preflight(name: str, request: Request, db: Session = Depends(get_db), user: User = Depends(require_platform("platform_admin_backup"))):
    path = _safe_backup(name); connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try: result = connection.execute("PRAGMA integrity_check").fetchone()[0]; tables = connection.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    finally: connection.close()
    valid = result == "ok" and tables > 0; append_audit(db, actor=user.username, action="backup.preflight", entity_type="backup", details={"name": path.name, "valid": valid, "table_count": tables}, **_audit_context(request)); db.commit()
    return {"valid": valid, "integrity": result, "table_count": tables, "restore_supported": False, "workflow": "Stop the backend, create a safety backup, validate canonical DB_PATH, then use the offline restore script under administrator supervision."}


def _audit_payload(row: AuditLog) -> dict[str, Any]:
    try: metadata = json.loads(row.details or "{}")
    except json.JSONDecodeError: metadata = {"details": row.details}
    if not isinstance(metadata, dict):
        metadata = {"details": metadata}
    return {"id": row.id, "actor": row.username, "action": row.action, "entity_type": row.entity_type, "entity_id": row.entity_id, "timestamp": row.created_at, "module": metadata.get("module", "legacy"), "result": metadata.get("result", "success"), "ip_address": metadata.get("ip_address", ""), "correlation_id": metadata.get("correlation_id", ""), "details": redact(metadata.get("details", metadata))}


@router.get("/audit")
def audit(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), actor: str = "", action: str = "", module: str = "", result: str = "", date_from: datetime | None = None, date_to: datetime | None = None, db: Session = Depends(get_db), _: User = Depends(require_platform("platform_admin_audit"))):
    query = db.query(AuditLog)
    if actor: query = query.filter(AuditLog.username.ilike(f"%{actor}%"))
    if action: query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    if date_from: query = query.filter(AuditLog.created_at >= date_from)
    if date_to: query = query.filter(AuditLog.created_at <= date_to)
    rows = query.order_by(AuditLog.id.desc()).all(); items = [_audit_payload(row) for row in rows]
    if module: items = [item for item in items if item["module"] == module]
    if result: items = [item for item in items if item["result"] == result]
    total = len(items); start = (page - 1) * page_size
    return {"items": items[start:start + page_size], "total": total, "page": page, "page_size": page_size}


@router.get("/audit/export.csv")
def audit_csv(db: Session = Depends(get_db), _: User = Depends(require_platform("platform_admin_audit"))):
    output = io.StringIO(newline=""); writer = csv.writer(output); writer.writerow(["timestamp", "actor", "action", "module", "entity_type", "entity_id", "result", "ip_address", "correlation_id"])
    safe = lambda value: f"'{value}" if str(value).startswith(("=", "+", "-", "@")) else value
    for row in db.query(AuditLog).order_by(AuditLog.id.desc()).limit(10000):
        item = _audit_payload(row); writer.writerow([safe(item["timestamp"]), safe(item["actor"]), safe(item["action"]), safe(item["module"]), safe(item["entity_type"]), item["entity_id"], safe(item["result"]), safe(item["ip_address"]), safe(item["correlation_id"])])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=platform-audit.csv"})


@router.get("/security")
def security(db: Session = Depends(get_db), _: User = Depends(require_platform("platform_admin_security"))):
    result = get_versioned_setting(db, "platform.security", SECURITY_DEFAULTS); result["effective_cors_origins"] = parse_cors_origins()
    sessions = db.query(UserIdentitySession, User.username).join(User, User.id == UserIdentitySession.user_id).filter(UserIdentitySession.is_active.is_(True)).order_by(UserIdentitySession.last_seen_at.desc()).limit(100).all()
    result["active_sessions"] = [{"id": session.id, "username": username, "device": session.device, "browser": session.browser, "ip_address": session.ip_address, "last_seen_at": session.last_seen_at} for session, username in sessions]
    return result


@router.put("/security")
def save_security(payload: SecurityUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_platform("platform_admin_security"))):
    if payload.confirmation != "APPLY SECURITY POLICY": raise HTTPException(400, "Exact confirmation phrase required")
    values = payload.model_dump(exclude={"version", "confirmation"})
    if os.getenv("ENVIRONMENT", "development").lower() == "production" and not values["secure_cookie_required"]: raise HTTPException(409, "Secure-cookie expectation cannot be disabled in production")
    try: result = put_versioned_setting(db, "platform.security", values, payload.version)
    except ValueError as exc: raise HTTPException(409, str(exc)) from exc
    append_audit(db, actor=user.username, action="security.policy_update", entity_type="security_policy", details=values, **_audit_context(request)); db.commit(); return result


@router.get("/system")
def system(db: Session = Depends(get_db), _: User = Depends(require_platform("platform_admin_view"))):
    database_ok = True
    try: db.execute(text("SELECT 1"))
    except Exception: database_ok = False
    latest = max((path.stat().st_mtime for path in (BACKUP_PATH / "platform").glob("*.db")), default=None) if (BACKUP_PATH / "platform").exists() else None
    storage = os.statvfs(str(BACKUP_PATH)) if hasattr(os, "statvfs") else None
    return {"application_version": "2.0.0", "environment": os.getenv("ENVIRONMENT", "development"), "database": {"engine": "sqlite" if DATABASE_URL.startswith("sqlite") else "postgresql", "connected": database_ok}, "schema": {"status": "available" if database_ok else "unavailable"}, "backup": {"latest_at": datetime.utcfromtimestamp(latest).isoformat() if latest else None}, "backend": {"status": "healthy" if database_ok else "degraded"}, "frontend": {"build": os.getenv("FRONTEND_BUILD_ID", "not configured")}, "storage": {"available_bytes": storage.f_bavail * storage.f_frsize if storage else None}, "scheduler": {"status": "not configured"}}


@router.get("/about")
def about(db: Session = Depends(get_db), _: User = Depends(require_platform("platform_admin_view"))):
    branding = get_branding(db); schema_tables = db.execute(text("SELECT count(*) FROM sqlite_master WHERE type='table'" if DATABASE_URL.startswith("sqlite") else "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" )).scalar()
    return {"product_name": branding.get("app_name", "Velcore ERP"), "version": "2.0.0", "build": os.getenv("APP_BUILD_ID", "not configured"), "schema": {"table_count": schema_tables}, "license": None, "copyright": None, "links": [], "third_party_notices": "See frontend/package-lock.json and backend requirements metadata."}
