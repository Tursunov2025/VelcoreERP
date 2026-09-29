"""System-wide branding settings stored in system_settings."""

import json

from sqlalchemy.orm import Session

from models import SystemSetting

DEFAULT_BRANDING = {
    "app_name": "Velcore ERP",
    "tagline": "Professional CRM / ERP tizimi",
    "logo_main": "",
    "logo_login": "",
    "logo_sidebar": "",
    "favicon": "",
    "color_primary": "#000000",
    "color_secondary": "#ffffff",
    "color_background": "#f5f6fa",
    "color_sidebar": "#000000",
    "color_button": "#000000",
    "color_button_text": "#ffffff",
    "color_secondary_button": "#ffffff",
    "color_secondary_button_text": "#111827",
    "color_card": "#ffffff",
    "color_sidebar_text": "#ffffff",
    "color_sidebar_active": "#ffffff",
    "color_sidebar_active_text": "#111827",
    "color_header": "#ffffff",
    "color_heading": "#111827",
    "color_text": "#111827",
    "color_muted": "#6b7280",
    "color_link": "#2563eb",
    "color_input_background": "#ffffff",
    "color_input_text": "#111827",
    "color_input_border": "#d1d5db",
    "color_table_header": "#f8fafc",
    "color_table_header_text": "#475569",
    "color_table_row": "#ffffff",
    "color_border": "#e5e7eb",
    "color_success": "#22c55e",
    "color_warning": "#f59e0b",
    "color_danger": "#ef4444",
    "color_info": "#3b82f6",
    "color_focus": "#2563eb",
    "font_scale": "1",
    "reduced_motion": "false",
    "button_radius": "16",
    "button_shadow": "true",
    "button_style": "rounded",
    "animations_enabled": "true",
    "anim_page_transitions": "true",
    "anim_modals": "true",
    "anim_loading": "true",
    "emoji_enabled": "true",
    "emoji_dashboard": "📊",
    "emoji_production": "🏭",
    "emoji_orders": "📋",
    "emoji_warehouse": "📦",
    "emoji_shipping": "🚚",
    "emoji_chat": "💬",
    "emoji_tasks": "✅",
    "emoji_operators": "👷",
    "emoji_analytics": "📈",
    "emoji_finance": "💰",
    "emoji_settings": "⚙️",
    "emoji_llp": "📁",
    "emoji_mes": "🏭",
    "theme_mode": "light",
    "language": "uz_latn",
    "clock_format": "24h",
    "clock_timezone": "Asia/Tashkent",
}

BRANDING_DB_PREFIX = "brand_"


def _db_key(field: str) -> str:
    return f"{BRANDING_DB_PREFIX}{field}"


def _field_from_db_key(key: str) -> str | None:
    if key.startswith(BRANDING_DB_PREFIX):
        return key[len(BRANDING_DB_PREFIX) :]
    return None


def get_branding(db: Session) -> dict:
    rows = db.query(SystemSetting).filter(SystemSetting.key.like(f"{BRANDING_DB_PREFIX}%")).all()
    data = dict(DEFAULT_BRANDING)
    for row in rows:
        field = _field_from_db_key(row.key)
        if field in data:
            data[field] = row.value
    appearance = db.query(SystemSetting).filter(SystemSetting.key == "platform.appearance").first()
    if appearance and appearance.value:
        try:
            extra = json.loads(appearance.value)
        except (TypeError, json.JSONDecodeError):
            extra = {}
        for field in ("short_name", "interface_density", "login_footer"):
            if field in extra:
                data[field] = extra[field]
    return data


def update_branding(db: Session, payload: dict) -> dict:
    for field, value in payload.items():
        if field not in DEFAULT_BRANDING:
            continue
        key = _db_key(field)
        str_value = str(value) if value is not None else ""
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if row:
            row.value = str_value
        else:
            db.add(SystemSetting(key=key, value=str_value))

    if "app_name" in payload:
        _sync_legacy_company_name(db, payload["app_name"])

    db.commit()
    from services.settings_cache import refresh_settings_cache

    refresh_settings_cache(db)
    return get_branding(db)


def reset_branding(db: Session) -> dict:
    db.query(SystemSetting).filter(SystemSetting.key.like(f"{BRANDING_DB_PREFIX}%")).delete(
        synchronize_session=False
    )
    _sync_legacy_company_name(db, DEFAULT_BRANDING["app_name"])
    db.commit()
    from services.settings_cache import refresh_settings_cache

    refresh_settings_cache(db)
    return get_branding(db)


def _sync_legacy_company_name(db: Session, name: str) -> None:
    """Keep company_name in sync for legacy references (telegram, system tab)."""
    row = db.query(SystemSetting).filter(SystemSetting.key == "company_name").first()
    if row:
        row.value = name
    else:
        db.add(SystemSetting(key="company_name", value=name))
