"""Super Admin CMS API — navigation, modules, themes, widgets, forms, audit, rollback."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.deps import get_current_user, require_admin
from database import get_db
from models import AuditLog, ModuleSetting, NavigationItem, Role, RolePermission, Theme, User, Widget
from services.audit import log_action, log_value_change
from services.super_admin_service import (
    create_snapshot,
    get_admin_full_config,
    get_runtime_config,
    invalidate_super_admin_cache,
    rollback_to_version,
    seed_super_admin_defaults,
    upsert_ui_setting,
    _json_dump,
    _json_load,
)

router = APIRouter(prefix="/super-admin", tags=["super-admin"])


def _is_super_admin(user: User) -> bool:
    return user.role in ("admin", "super_admin") or user.department == "Admin"


def _require_super_admin(user: User = Depends(get_current_user)) -> User:
    if not _is_super_admin(user):
        raise HTTPException(status_code=403, detail="Super Admin access required")
    return user


class NavItemIn(BaseModel):
    nav_key: str
    label: str
    icon: str = ""
    emoji: str = ""
    path: str = "/"
    color: str = ""
    sort_order: int = 0
    parent_id: int | None = None
    visible: bool = True
    hidden: bool = False
    permissions: list[str] = Field(default_factory=list)
    module_key: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class NavItemUpdate(BaseModel):
    label: str | None = None
    icon: str | None = None
    emoji: str | None = None
    path: str | None = None
    color: str | None = None
    sort_order: int | None = None
    parent_id: int | None = None
    visible: bool | None = None
    hidden: bool | None = None
    permissions: list[str] | None = None
    module_key: str | None = None
    config: dict[str, Any] | None = None


class ModuleIn(BaseModel):
    module_key: str
    label: str
    icon: str = ""
    color: str = ""
    url: str = "/"
    enabled: bool = True
    permissions: list[str] = Field(default_factory=list)
    sort_order: int = 0


class WidgetIn(BaseModel):
    widget_key: str
    title: str
    widget_type: str = "stat"
    enabled: bool = True
    sort_order: int = 0
    color: str = ""
    layout: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


class ThemeIn(BaseModel):
    name: str
    is_dark: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class FormSchemaIn(BaseModel):
    form_key: str
    title: str
    fields: list[dict[str, Any]] = Field(default_factory=list)


class TableSchemaIn(BaseModel):
    table_key: str
    title: str
    columns: list[dict[str, Any]] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    export: list[str] = Field(default_factory=lambda: ["excel", "pdf"])


class RolePermissionsIn(BaseModel):
    permissions: dict[str, bool]


class ReorderItem(BaseModel):
    id: int
    sort_order: int


class SnapshotIn(BaseModel):
    label: str = ""


@router.get("/config")
def admin_config(db: Session = Depends(get_db), user: User = Depends(_require_super_admin)):
    seed_super_admin_defaults(db)
    return get_admin_full_config(db)


@router.get("/runtime")
def runtime_config(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_runtime_config(db)


@router.post("/navigation")
def create_navigation(
    payload: NavItemIn,
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    if db.query(NavigationItem).filter(NavigationItem.nav_key == payload.nav_key).first():
        raise HTTPException(status_code=400, detail="nav_key already exists")
    item = NavigationItem(
        nav_key=payload.nav_key.strip(),
        label=payload.label.strip(),
        icon=payload.icon,
        emoji=payload.emoji,
        path=payload.path,
        color=payload.color,
        sort_order=payload.sort_order,
        parent_id=payload.parent_id,
        visible=payload.visible,
        hidden=payload.hidden,
        permissions_json=_json_dump(payload.permissions),
        module_key=payload.module_key,
        config_json=_json_dump(payload.config),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    create_snapshot(db, user.username, f"Nav add: {item.nav_key}")
    log_action(db, user.username, "create", "navigation_item", item.id, item.nav_key)
    db.commit()
    invalidate_super_admin_cache()
    return {"id": item.id, "nav_key": item.nav_key}


@router.put("/navigation/{item_id}")
def update_navigation(
    item_id: int,
    payload: NavItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    item = db.query(NavigationItem).filter(NavigationItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    data = payload.model_dump(exclude_unset=True)
    perms = data.pop("permissions", None)
    cfg = data.pop("config", None)
    for k, v in data.items():
        old = getattr(item, k)
        setattr(item, k, v)
        log_value_change(db, user.username, "update", "navigation_item", item.id, k, old, v)
    if perms is not None:
        old = item.permissions_json
        item.permissions_json = _json_dump(perms)
        log_value_change(db, user.username, "update", "navigation_item", item.id, "permissions", old, perms)
    if cfg is not None:
        item.config_json = _json_dump(cfg)
    db.commit()
    invalidate_super_admin_cache()
    return {"message": "updated"}


@router.delete("/navigation/{item_id}")
def delete_navigation(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    item = db.query(NavigationItem).filter(NavigationItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    create_snapshot(db, user.username, f"Pre-delete nav {item.nav_key}")
    log_action(db, user.username, "delete", "navigation_item", item.id, item.nav_key)
    db.delete(item)
    db.commit()
    invalidate_super_admin_cache()
    return {"message": "deleted"}


@router.put("/navigation/reorder")
def reorder_navigation(
    order: list[ReorderItem],
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    for row in order:
        item = db.query(NavigationItem).filter(NavigationItem.id == row.id).first()
        if item:
            item.sort_order = row.sort_order
    db.commit()
    invalidate_super_admin_cache()
    return {"message": "reordered"}


@router.put("/modules/{module_id}")
def update_module(
    module_id: int,
    payload: ModuleIn,
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    mod = db.query(ModuleSetting).filter(ModuleSetting.id == module_id).first()
    if not mod:
        raise HTTPException(status_code=404, detail="Not found")
    mod.label = payload.label
    mod.icon = payload.icon
    mod.color = payload.color
    mod.url = payload.url
    mod.enabled = payload.enabled
    mod.permissions_json = _json_dump(payload.permissions)
    mod.sort_order = payload.sort_order
    db.commit()
    invalidate_super_admin_cache()
    log_action(db, user.username, "update", "module_setting", mod.id, mod.module_key)
    db.commit()
    return {"message": "updated"}


@router.post("/widgets")
def upsert_widget(
    payload: WidgetIn,
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    w = db.query(Widget).filter(Widget.widget_key == payload.widget_key).first()
    if not w:
        w = Widget(widget_key=payload.widget_key)
        db.add(w)
    w.title = payload.title
    w.widget_type = payload.widget_type
    w.enabled = payload.enabled
    w.sort_order = payload.sort_order
    w.color = payload.color
    w.layout_json = _json_dump(payload.layout)
    w.config_json = _json_dump(payload.config)
    db.commit()
    invalidate_super_admin_cache()
    return {"widget_key": w.widget_key}


@router.delete("/widgets/{widget_key}")
def delete_widget(
    widget_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    w = db.query(Widget).filter(Widget.widget_key == widget_key).first()
    if w:
        db.delete(w)
        db.commit()
    invalidate_super_admin_cache()
    return {"message": "deleted"}


@router.post("/themes")
def create_theme(
    payload: ThemeIn,
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    theme = Theme(
        name=payload.name,
        is_dark=payload.is_dark,
        config_json=_json_dump(payload.config),
    )
    db.add(theme)
    db.commit()
    db.refresh(theme)
    return {"id": theme.id}


@router.post("/themes/{theme_id}/activate")
def activate_theme(
    theme_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Not found")
    for t in db.query(Theme).all():
        t.is_active = t.id == theme_id
    db.commit()
    invalidate_super_admin_cache()
    return {"message": "activated", "theme_id": theme_id}


@router.put("/themes/{theme_id}")
def update_theme(
    theme_id: int,
    payload: ThemeIn,
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Not found")
    theme.name = payload.name
    theme.is_dark = payload.is_dark
    theme.config_json = _json_dump(payload.config)
    db.commit()
    invalidate_super_admin_cache()
    return {"message": "updated"}


@router.get("/forms")
def list_forms(db: Session = Depends(get_db), user: User = Depends(_require_super_admin)):
    from models import UiSetting

    row = db.query(UiSetting).filter(UiSetting.key == "dynamic_forms_json").first()
    return {"forms": _json_load(row.value if row else None, [])}


@router.put("/forms")
def save_forms(
    forms: list[FormSchemaIn],
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    data = [f.model_dump() for f in forms]
    upsert_ui_setting(db, "dynamic_forms_json", data, "forms", user.username)
    return {"forms": data}


@router.get("/tables")
def list_tables(db: Session = Depends(get_db), user: User = Depends(_require_super_admin)):
    from models import UiSetting

    row = db.query(UiSetting).filter(UiSetting.key == "dynamic_tables_json").first()
    return {"tables": _json_load(row.value if row else None, [])}


@router.put("/tables")
def save_tables(
    tables: list[TableSchemaIn],
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    data = [t.model_dump() for t in tables]
    upsert_ui_setting(db, "dynamic_tables_json", data, "tables", user.username)
    return {"tables": data}


@router.put("/roles/{role_id}/permissions")
def update_role_permissions(
    role_id: int,
    payload: RolePermissionsIn,
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
    for key, enabled in payload.permissions.items():
        db.add(RolePermission(role_id=role_id, permission_key=key, enabled=bool(enabled)))
    db.commit()
    log_action(db, user.username, "update", "role_permissions", role_id, role.role_key)
    db.commit()
    return {"message": "updated"}


@router.get("/audit-logs")
def super_admin_audit_logs(
    limit: int = 100,
    entity_type: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    q = db.query(AuditLog).order_by(AuditLog.id.desc())
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    rows = q.limit(min(limit, 500)).all()
    return {
        "logs": [
            {
                "id": r.id,
                "username": r.username,
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "details": r.details,
                "old_value": r.old_value,
                "new_value": r.new_value,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.post("/snapshot")
def take_snapshot(
    payload: SnapshotIn,
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    v = create_snapshot(db, user.username, payload.label)
    return {"id": v.id, "label": v.label}


@router.post("/rollback/{version_id}")
def rollback(
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_require_super_admin),
):
    try:
        return rollback_to_version(db, version_id, user.username)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
