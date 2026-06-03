import json
import os

from sqlalchemy.orm import Session

from constants import DEPARTMENTS, NOTIFICATION_EVENTS, PRODUCTION_STAGES
from models import SystemSetting
from services.control_center_config import (
    DEFAULT_DASHBOARD_WIDGETS,
    DEFAULT_MOBILE_APP,
    DEFAULT_NAV_VISIBILITY,
    serialize_dashboard_widgets,
    serialize_mobile_app,
    serialize_nav_visibility,
)
from services.materials_warehouse import DEFAULT_CATEGORIES
from services.settings_cache import invalidate_settings_cache, refresh_settings_cache

# --- Default values (source of truth when DB row missing) ---

DEFAULT_SETTINGS: dict[str, str] = {
    # Company
    "company_name": "Velcore ERP",
    "company_phone": "",
    "company_email": "",
    "company_address": "",
    "company_tax_id": "",
    "company_currency": "so'm",
    "company_logo_url": "",
    # Production
    "production_stages_json": json.dumps(PRODUCTION_STAGES, ensure_ascii=False),
    "departments_json": json.dumps(DEPARTMENTS, ensure_ascii=False),
    "mes_job_default_priority": "normal",
    "mes_inspection_stage": "Tekshiruv",
    "mes_final_stage": "Tayyor",
    "mes_default_stages_json": json.dumps(
        [
            ["Lazer", "Kesish"],
            ["Svarshik", "Svarka"],
            ["Kraska", "Kraska"],
            ["Nazorat", "Tekshiruv"],
            ["Upakovka", "Upakovka"],
            ["Sklad", "Ombor"],
            ["Yuklash", "Ombor"],
        ],
        ensure_ascii=False,
    ),
    # Telegram + notifications
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "notifications_enabled": "true",
    "telegram_notifications_enabled": "true",
    # Warehouse
    "warehouse_low_stock_alerts": "true",
    "warehouse_finished_goods_prefix": "A",
    "warehouse_dispatch_requires_approval": "false",
    "warehouse_default_receipt_notes": "",
    # Materials
    "materials_default_unit": "dona",
    "materials_low_stock_default": "5",
    "materials_auto_consume_enabled": "true",
    "materials_auto_consume_stages_json": json.dumps(["Lazer", "Kraska"], ensure_ascii=False),
    "materials_categories_json": json.dumps(
        [[code, name] for code, name in DEFAULT_CATEGORIES], ensure_ascii=False
    ),
    # Costing
    "costing_currency": "UZS",
    "costing_currency_symbol": "so'm",
    "costing_default_markup_pct": "0",
    "costing_track_job_material_cost": "true",
    # UI / auth / backup
    "jwt_access_minutes": "60",
    "jwt_refresh_days": "7",
    "auto_backup_enabled": "false",
    "auto_backup_interval_hours": "24",
    "backup_retention_count": "30",
    "backup_include_uploads": "true",
    "migration_include_settings": "true",
    # Super Admin / Executive control center
    "nav_visibility_json": serialize_nav_visibility(DEFAULT_NAV_VISIBILITY),
    "dashboard_widgets_json": serialize_dashboard_widgets(DEFAULT_DASHBOARD_WIDGETS),
    "mobile_app_json": serialize_mobile_app(DEFAULT_MOBILE_APP),
    "label_printers_json": "[]",
}

for _event in NOTIFICATION_EVENTS:
    DEFAULT_SETTINGS[f"notify_{_event}"] = "true"

COMPANY_KEYS = frozenset(
    {
        "company_name",
        "company_phone",
        "company_email",
        "company_address",
        "company_tax_id",
        "company_currency",
        "company_logo_url",
    }
)

PRODUCTION_KEYS = frozenset(
    {
        "production_stages_json",
        "departments_json",
        "mes_job_default_priority",
        "mes_inspection_stage",
        "mes_final_stage",
        "mes_default_stages_json",
    }
)

WAREHOUSE_KEYS = frozenset(
    {
        "warehouse_low_stock_alerts",
        "warehouse_finished_goods_prefix",
        "warehouse_dispatch_requires_approval",
        "warehouse_default_receipt_notes",
    }
)

MATERIALS_KEYS = frozenset(
    {
        "materials_default_unit",
        "materials_low_stock_default",
        "materials_auto_consume_enabled",
        "materials_auto_consume_stages_json",
        "materials_categories_json",
    }
)

COSTING_KEYS = frozenset(
    {
        "costing_currency",
        "costing_currency_symbol",
        "costing_default_markup_pct",
        "costing_track_job_material_cost",
    }
)

BACKUP_KEYS = frozenset(
    {
        "auto_backup_enabled",
        "auto_backup_interval_hours",
        "backup_retention_count",
        "backup_include_uploads",
        "migration_include_settings",
        "jwt_access_minutes",
        "jwt_refresh_days",
    }
)

TELEGRAM_KEYS = frozenset(
    {
        "telegram_bot_token",
        "telegram_chat_id",
        "telegram_notifications_enabled",
        "notifications_enabled",
    }
)

NOTIFICATION_KEYS = frozenset({"notifications_enabled", "telegram_notifications_enabled"}) | {
    f"notify_{e}" for e in NOTIFICATION_EVENTS
}

SECRET_KEYS = frozenset({"telegram_bot_token"})

EXECUTIVE_KEYS = frozenset(
    {
        "nav_visibility_json",
        "dashboard_widgets_json",
        "mobile_app_json",
    }
)

LABEL_PRINTER_KEYS = frozenset({"label_printers_json"})

SETTING_GROUPS = {
    "company": COMPANY_KEYS,
    "production": PRODUCTION_KEYS,
    "telegram": TELEGRAM_KEYS,
    "warehouse": WAREHOUSE_KEYS,
    "materials": MATERIALS_KEYS,
    "costing": COSTING_KEYS,
    "backup": BACKUP_KEYS,
    "notifications": NOTIFICATION_KEYS,
    "executive": EXECUTIVE_KEYS,
    "label_printers": LABEL_PRINTER_KEYS,
}


def _merge_defaults(rows: list[SystemSetting]) -> dict[str, str]:
    data = dict(DEFAULT_SETTINGS)
    for row in rows:
        data[row.key] = row.value
    return data


def _mask_secrets(data: dict[str, str]) -> dict[str, str]:
    result = dict(data)
    for key in SECRET_KEYS:
        if key in result:
            result[key] = _mask_secret(result.get(key, ""))
    return result


def get_settings_for_admin(db: Session) -> dict[str, str]:
    rows = db.query(SystemSetting).all()
    return _merge_defaults(rows)


def get_all_settings(db: Session) -> dict[str, str]:
    return _mask_secrets(get_settings_for_admin(db))


def get_settings_group(db: Session, group: str) -> dict[str, str]:
    keys = SETTING_GROUPS.get(group)
    if not keys:
        raise ValueError(f"Unknown settings group: {group}")
    all_data = get_settings_for_admin(db)
    result = {k: all_data.get(k, DEFAULT_SETTINGS.get(k, "")) for k in keys}
    if group == "telegram":
        result["telegram_bot_token"] = _mask_secret(result.get("telegram_bot_token", ""))
    return result


def get_telegram_settings(db: Session) -> dict:
    return get_settings_group(db, "telegram")


def get_notification_settings(db: Session) -> dict:
    return get_settings_group(db, "notifications")


def update_settings(db: Session, payload: dict, *, allowed_keys: frozenset[str] | None = None) -> dict:
    whitelist = allowed_keys or frozenset(DEFAULT_SETTINGS.keys())
    for key, value in payload.items():
        if key not in whitelist:
            continue
        if key in SECRET_KEYS and value in ("", "••••••••"):
            continue
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        str_value = str(value) if value is not None else ""
        if row:
            row.value = str_value
        else:
            db.add(SystemSetting(key=key, value=str_value))
    db.commit()
    refresh_settings_cache(db)
    return get_settings_for_admin(db)


def update_settings_group(db: Session, group: str, payload: dict) -> dict:
    keys = SETTING_GROUPS.get(group)
    if not keys:
        raise ValueError(f"Unknown settings group: {group}")
    filtered = {k: v for k, v in payload.items() if k in keys}
    update_settings(db, filtered, allowed_keys=keys)
    result = get_settings_group(db, group)
    if group == "telegram":
        result["telegram_bot_token"] = _mask_secret(result.get("telegram_bot_token", ""))
    return result


def update_telegram_settings(db: Session, payload: dict) -> dict:
    return update_settings_group(db, "telegram", payload)


def update_notification_settings(db: Session, payload: dict) -> dict:
    return update_settings_group(db, "notifications", payload)


def export_settings_bundle(db: Session, *, include_branding: bool = True) -> dict:
    rows = db.query(SystemSetting).all()
    bundle: dict[str, str] = {}
    for row in rows:
        if row.key.startswith("brand_") and not include_branding:
            continue
        if row.key in SECRET_KEYS and row.value:
            bundle[row.key] = row.value
        else:
            bundle[row.key] = row.value
    for key, default in DEFAULT_SETTINGS.items():
        bundle.setdefault(key, default)
    return {
        "version": 1,
        "exported_at": __import__("datetime").datetime.utcnow().isoformat(),
        "settings": bundle,
    }


def import_settings_bundle(db: Session, bundle: dict, *, merge: bool = True) -> dict:
    settings = bundle.get("settings") if isinstance(bundle.get("settings"), dict) else bundle
    if not isinstance(settings, dict):
        raise ValueError("Invalid settings bundle")
    allowed = frozenset(DEFAULT_SETTINGS.keys())
    if not merge:
        for key in list(settings.keys()):
            if key.startswith("brand_"):
                allowed = allowed | {key}
    payload = {k: v for k, v in settings.items() if k in allowed or k.startswith("brand_")}
    for key, value in payload.items():
        if key in SECRET_KEYS and value in ("", "••••••••"):
            continue
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        str_value = str(value) if value is not None else ""
        if row:
            row.value = str_value
        else:
            db.add(SystemSetting(key=key, value=str_value))
    db.commit()
    refresh_settings_cache(db)
    return get_settings_for_admin(db)


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    return "••••••••" if len(value) > 4 else "****"
