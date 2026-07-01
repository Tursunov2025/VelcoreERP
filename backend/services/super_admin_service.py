"""Velcore ERP — Super Admin CMS (navigation, modules, themes, widgets, versioning)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from constants import ALL_PERMISSION_KEYS
from models import (
    FeatureFlag,
    ModuleSetting,
    NavigationItem,
    PermissionDefinition,
    Role,
    RolePermission,
    Theme,
    UiConfigVersion,
    UiSetting,
    Widget,
)
from services.audit import log_action, log_value_change
from services.settings_cache import invalidate_settings_cache

DEFAULT_ROLES = [
    ("super_admin", "Super Admin", "To'liq tizim boshqaruvi", True, 1),
    ("admin", "Admin", "Administrator", True, 2),
    ("director", "Direktor", "Rahbariyat", True, 3),
    ("operator", "Operator", "Ishlab chiqarish operatori", True, 4),
    ("warehouse_keeper", "Omborchi", "Ombor xodimi", True, 5),
    ("technologist", "Texnolog", "Texnologiya bo'limi", True, 6),
    ("driver", "Haydovchi", "Transport haydovchisi", True, 7),
    ("accountant", "Buxgalter", "Moliya bo'limi", True, 8),
    ("qc_inspector", "Sifat nazoratchisi", "QC / sifat nazorati", True, 9),
]

DEFAULT_MODULES = [
    ("crm", "CRM", "👥", "#6366f1", "/crm", 1),
    ("warehouse", "Ombor", "📦", "#f59e0b", "/warehouse", 2),
    ("production", "Ishlab chiqarish", "🏭", "#ef4444", "/production", 3),
    ("technology", "Texnologiya", "📋", "#8b5cf6", "/mes/templates", 4),
    ("logistics", "Logistika", "🚚", "#0ea5e9", "/logistics", 5),
    ("finance", "Moliya", "💰", "#22c55e", "/finance", 6),
    ("llp", "LLP", "📄", "#64748b", "/logistics/llp", 7),
    ("gps", "GPS", "🛰️", "#14b8a6", "/logistics/gps", 8),
    ("driver", "Driver", "📱", "#a855f7", "/driver", 9),
    ("qc", "Sifat nazorati", "✅", "#ec4899", "/mes/terminal/qc", 10),
]

DEFAULT_NAV = [
    ("dashboard", "Dashboard", "🏠", "/", None, 1, "dashboard"),
    ("crm", "CRM", "👥", "/crm", None, 2, "crm"),
    ("crmLedger", "Mijozlar qarzdorligi", "", "/crm", "crm", 1, "crm"),
    ("orders", "Zakazlar", "📦", "/orders", None, 3, "orders"),
    ("production", "Ishlab chiqarish", "🏭", "/production", None, 4, "production"),
    ("warehouse", "Ombor", "📦", "/warehouse", None, 5, "warehouse"),
    ("exportLogistics", "Export va Logistika", "🚚", "/logistics", None, 6, "logistics"),
    ("logisticsDashboard", "Dashboard", "", "/logistics", "exportLogistics", 1, "logistics"),
    ("finishedWarehouse", "Tayyor Mahsulot Ombori", "", "/logistics/finished-warehouse", "exportLogistics", 2, "logistics"),
    ("finance", "Moliya", "💰", "/finance", None, 7, "finance"),
    ("settings", "Sozlamalar", "⚙️", "/settings", None, 99, "settings"),
]

DEFAULT_WIDGETS = [
    ("order_stats", "Buyurtmalar", "stat", 1, "#6366f1"),
    ("clock", "Soat", "clock", 2, "#64748b"),
    ("online_operators", "Online operatorlar", "list", 3, "#22c55e"),
    ("production_chart", "Ishlab chiqarish", "chart", 4, "#f59e0b"),
    ("export_shipments", "Export yuklar", "stat", 5, "#0ea5e9"),
    ("currency_rates", "Valyuta kurslari", "stat", 6, "#8b5cf6"),
    ("top_debtors", "Qarzdorlar", "table", 7, "#ef4444"),
    ("warehouse_forecast", "Ombor prognozi", "alert", 8, "#14b8a6"),
]

DEFAULT_THEME = {
    "primary_color": "#1e3a8a",
    "secondary_color": "#dbeafe",
    "sidebar_color": "#0f172a",
    "card_color": "#ffffff",
    "button_color": "#2563eb",
    "background_color": "#f1f5f9",
    "text_color": "#0f172a",
    "font_size_base": "14px",
    "border_radius": "16px",
    "animations_enabled": True,
}


def _json_load(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def _json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def invalidate_super_admin_cache() -> None:
    invalidate_settings_cache()


def seed_super_admin_defaults(db: Session) -> None:
    """Idempotent seed for roles, permissions, modules, navigation, widgets, theme."""
    for role_key, label, desc, is_system, order in DEFAULT_ROLES:
        if not db.query(Role).filter(Role.role_key == role_key).first():
            db.add(
                Role(
                    role_key=role_key,
                    label=label,
                    description=desc,
                    is_system=is_system,
                    sort_order=order,
                )
            )
    db.flush()

    for key in ALL_PERMISSION_KEYS:
        if not db.query(PermissionDefinition).filter(PermissionDefinition.perm_key == key).first():
            db.add(
                PermissionDefinition(
                    perm_key=key,
                    label=key.replace("_", " ").title(),
                    module=key.split("_")[0] if "_" in key else "general",
                )
            )

    super_role = db.query(Role).filter(Role.role_key == "super_admin").first()
    if super_role:
        for key in ALL_PERMISSION_KEYS:
            exists = (
                db.query(RolePermission)
                .filter(RolePermission.role_id == super_role.id, RolePermission.permission_key == key)
                .first()
            )
            if not exists:
                db.add(RolePermission(role_id=super_role.id, permission_key=key, enabled=True))

    for mod_key, label, icon, color, url, order in DEFAULT_MODULES:
        if not db.query(ModuleSetting).filter(ModuleSetting.module_key == mod_key).first():
            db.add(
                ModuleSetting(
                    module_key=mod_key,
                    label=label,
                    icon=icon,
                    color=color,
                    url=url,
                    sort_order=order,
                    enabled=True,
                )
            )

    parent_map: dict[str, int] = {}
    for nav_key, label, emoji, path, parent_key, order, module_key in DEFAULT_NAV:
        if db.query(NavigationItem).filter(NavigationItem.nav_key == nav_key).first():
            continue
        parent_id = parent_map.get(parent_key) if parent_key else None
        item = NavigationItem(
            nav_key=nav_key,
            label=label,
            emoji=emoji,
            path=path,
            parent_id=parent_id,
            sort_order=order,
            module_key=module_key,
            visible=True,
            hidden=False,
        )
        db.add(item)
        db.flush()
        parent_map[nav_key] = item.id

    for wkey, title, wtype, order, color in DEFAULT_WIDGETS:
        if not db.query(Widget).filter(Widget.widget_key == wkey).first():
            db.add(
                Widget(
                    widget_key=wkey,
                    title=title,
                    widget_type=wtype,
                    sort_order=order,
                    color=color,
                    enabled=True,
                )
            )

    if not db.query(Theme).filter(Theme.is_active.is_(True)).first():
        db.add(
            Theme(
                name="Velcore Default",
                is_active=True,
                is_dark=False,
                config_json=_json_dump(DEFAULT_THEME),
            )
        )

    for flag_key, enabled, desc in [
        ("traceability_enabled", False, "Package traceability module"),
        ("print_agent_enabled", False, "Label print agent"),
        ("driver_app_enabled", True, "Velcore Driver mobile app"),
    ]:
        if not db.query(FeatureFlag).filter(FeatureFlag.flag_key == flag_key).first():
            db.add(FeatureFlag(flag_key=flag_key, enabled=enabled, description=desc))

    db.commit()


def _serialize_nav(item: NavigationItem, children: list | None = None) -> dict:
    return {
        "id": item.id,
        "nav_key": item.nav_key,
        "label": item.label,
        "icon": item.icon,
        "emoji": item.emoji,
        "path": item.path,
        "color": item.color,
        "sort_order": item.sort_order,
        "parent_id": item.parent_id,
        "visible": item.visible,
        "hidden": item.hidden,
        "permissions": _json_load(item.permissions_json, []),
        "module_key": item.module_key,
        "config": _json_load(item.config_json, {}),
        "children": children or [],
    }


def get_navigation_tree(db: Session) -> list[dict]:
    items = db.query(NavigationItem).order_by(NavigationItem.sort_order, NavigationItem.id).all()
    by_id = {i.id: _serialize_nav(i) for i in items}
    roots: list[dict] = []
    for item in items:
        node = by_id[item.id]
        if item.parent_id and item.parent_id in by_id:
            by_id[item.parent_id]["children"].append(node)
        else:
            roots.append(node)
    for node in by_id.values():
        node["children"].sort(key=lambda c: (c.get("sort_order", 0), c.get("id", 0)))
    roots.sort(key=lambda r: (r.get("sort_order", 0), r.get("id", 0)))
    return roots


def get_runtime_config(db: Session) -> dict[str, Any]:
    """Merged config for all authenticated users — no server restart needed."""
    theme = db.query(Theme).filter(Theme.is_active.is_(True)).first()
    widgets = (
        db.query(Widget)
        .filter(Widget.enabled.is_(True))
        .order_by(Widget.sort_order)
        .all()
    )
    modules = (
        db.query(ModuleSetting)
        .filter(ModuleSetting.enabled.is_(True))
        .order_by(ModuleSetting.sort_order)
        .all()
    )
    flags = {f.flag_key: f.enabled for f in db.query(FeatureFlag).all()}
    forms_row = db.query(UiSetting).filter(UiSetting.key == "dynamic_forms_json").first()
    tables_row = db.query(UiSetting).filter(UiSetting.key == "dynamic_tables_json").first()
    forms = _json_load(forms_row.value if forms_row else None, [])
    tables = _json_load(tables_row.value if tables_row else None, [])

    nav_tree = get_navigation_tree(db)
    visible_nav = [n for n in nav_tree if n.get("visible") and not n.get("hidden")]

    nav_visibility: dict[str, bool] = {}
    for item in db.query(NavigationItem).all():
        nav_visibility[item.nav_key] = bool(item.visible and not item.hidden)

    dashboard_widgets = [
        {
            "id": w.widget_key,
            "enabled": w.enabled,
            "order": w.sort_order,
            "title": w.title,
            "type": w.widget_type,
            "color": w.color,
            "layout": _json_load(w.layout_json, {}),
            "config": _json_load(w.config_json, {}),
        }
        for w in widgets
    ]

    return {
        "navigation": visible_nav,
        "nav_visibility": nav_visibility,
        "dashboard_widgets": dashboard_widgets,
        "modules": [
            {
                "module_key": m.module_key,
                "label": m.label,
                "icon": m.icon,
                "color": m.color,
                "url": m.url,
                "permissions": _json_load(m.permissions_json, []),
            }
            for m in modules
        ],
        "theme": _json_load(theme.config_json, DEFAULT_THEME) if theme else DEFAULT_THEME,
        "theme_dark": theme.is_dark if theme else False,
        "feature_flags": flags,
        "dynamic_forms": forms,
        "dynamic_tables": tables,
    }


def get_admin_full_config(db: Session) -> dict[str, Any]:
    runtime = get_runtime_config(db)
    roles = db.query(Role).order_by(Role.sort_order).all()
    return {
        **runtime,
        "navigation_all": get_navigation_tree(db),
        "widgets_all": [
            {
                "id": w.id,
                "widget_key": w.widget_key,
                "title": w.title,
                "widget_type": w.widget_type,
                "enabled": w.enabled,
                "sort_order": w.sort_order,
                "color": w.color,
                "layout": _json_load(w.layout_json, {}),
                "config": _json_load(w.config_json, {}),
            }
            for w in db.query(Widget).order_by(Widget.sort_order).all()
        ],
        "modules_all": [
            {
                "id": m.id,
                "module_key": m.module_key,
                "enabled": m.enabled,
                "label": m.label,
                "icon": m.icon,
                "color": m.color,
                "url": m.url,
                "permissions": _json_load(m.permissions_json, []),
                "sort_order": m.sort_order,
            }
            for m in db.query(ModuleSetting).order_by(ModuleSetting.sort_order).all()
        ],
        "themes": [
            {
                "id": t.id,
                "name": t.name,
                "is_active": t.is_active,
                "is_dark": t.is_dark,
                "config": _json_load(t.config_json, {}),
            }
            for t in db.query(Theme).all()
        ],
        "roles": [
            {
                "id": r.id,
                "role_key": r.role_key,
                "label": r.label,
                "description": r.description,
                "is_system": r.is_system,
                "permissions": {
                    rp.permission_key: rp.enabled
                    for rp in db.query(RolePermission).filter(RolePermission.role_id == r.id).all()
                },
            }
            for r in roles
        ],
        "permissions": [
            {
                "perm_key": p.perm_key,
                "label": p.label,
                "module": p.module,
                "description": p.description,
            }
            for p in db.query(PermissionDefinition).order_by(PermissionDefinition.module, PermissionDefinition.perm_key).all()
        ],
        "versions": [
            {
                "id": v.id,
                "label": v.label,
                "created_by": v.created_by,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in db.query(UiConfigVersion).order_by(UiConfigVersion.id.desc()).limit(50).all()
        ],
    }


def create_snapshot(db: Session, username: str, label: str = "") -> UiConfigVersion:
    snapshot = get_admin_full_config(db)
    version = UiConfigVersion(
        label=label or f"Snapshot {datetime.utcnow():%Y-%m-%d %H:%M}",
        snapshot_json=_json_dump(snapshot),
        created_by=username,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    log_action(db, username, "snapshot", "ui_config_version", version.id, label)
    db.commit()
    return version


def rollback_to_version(db: Session, version_id: int, username: str) -> dict:
    version = db.query(UiConfigVersion).filter(UiConfigVersion.id == version_id).first()
    if not version:
        raise ValueError("Version not found")
    create_snapshot(db, username, f"Pre-rollback backup #{version_id}")
    data = _json_load(version.snapshot_json, {})
    _apply_snapshot(db, data, username)
    invalidate_super_admin_cache()
    log_action(db, username, "rollback", "ui_config_version", version_id)
    db.commit()
    return get_runtime_config(db)


def _apply_snapshot(db: Session, data: dict, username: str) -> None:
    for nav in data.get("navigation_all") or []:
        item = db.query(NavigationItem).filter(NavigationItem.nav_key == nav.get("nav_key")).first()
        if item:
            item.label = nav.get("label", item.label)
            item.emoji = nav.get("emoji", item.emoji)
            item.path = nav.get("path", item.path)
            item.color = nav.get("color", item.color)
            item.sort_order = nav.get("sort_order", item.sort_order)
            item.visible = nav.get("visible", item.visible)
            item.hidden = nav.get("hidden", item.hidden)
            item.permissions_json = _json_dump(nav.get("permissions", []))
    for mod in data.get("modules_all") or []:
        row = db.query(ModuleSetting).filter(ModuleSetting.module_key == mod.get("module_key")).first()
        if row:
            row.enabled = mod.get("enabled", row.enabled)
            row.label = mod.get("label", row.label)
            row.icon = mod.get("icon", row.icon)
            row.color = mod.get("color", row.color)
            row.url = mod.get("url", row.url)
    db.commit()


def upsert_ui_setting(db: Session, key: str, value: Any, category: str, username: str) -> UiSetting:
    raw = _json_dump(value) if not isinstance(value, str) else value
    row = db.query(UiSetting).filter(UiSetting.key == key).first()
    old = row.value if row else ""
    if not row:
        row = UiSetting(key=key, value=raw, category=category, updated_by=username)
        db.add(row)
    else:
        row.value = raw
        row.category = category
        row.updated_by = username
        row.updated_at = datetime.utcnow()
    log_value_change(db, username, "update", "ui_setting", row.id, key, old, raw)
    db.commit()
    invalidate_super_admin_cache()
    return row
