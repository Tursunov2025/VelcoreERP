import json
import os

from sqlalchemy.orm import Session

from constants import NOTIFICATION_EVENTS
from models import SystemSetting

DEFAULT_SETTINGS = {
    "company_name": "Velcore ERP",
    "company_phone": "",
    "company_logo_url": "",
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "notifications_enabled": "true",
    "telegram_notifications_enabled": "true",
    "jwt_access_minutes": "60",
    "jwt_refresh_days": "7",
    "auto_backup_enabled": "false",
    "auto_backup_interval_hours": "24",
}

for _event in NOTIFICATION_EVENTS:
    DEFAULT_SETTINGS[f"notify_{_event}"] = "true"

TELEGRAM_KEYS = {
    "telegram_bot_token",
    "telegram_chat_id",
    "telegram_notifications_enabled",
    "notifications_enabled",
}

NOTIFICATION_KEYS = {"notifications_enabled", "telegram_notifications_enabled"} | {
    f"notify_{e}" for e in NOTIFICATION_EVENTS
}


def get_all_settings(db: Session) -> dict:
    rows = db.query(SystemSetting).all()
    data = dict(DEFAULT_SETTINGS)
    for row in rows:
        data[row.key] = row.value
    data["telegram_bot_token"] = _mask_secret(data.get("telegram_bot_token", ""))
    return data


def get_settings_for_admin(db: Session) -> dict:
    rows = db.query(SystemSetting).all()
    data = dict(DEFAULT_SETTINGS)
    for row in rows:
        data[row.key] = row.value
    return data


def get_telegram_settings(db: Session) -> dict:
    all_data = get_settings_for_admin(db)
    return {
        "telegram_bot_token": _mask_secret(all_data.get("telegram_bot_token", "")),
        "telegram_chat_id": all_data.get("telegram_chat_id", ""),
        "telegram_notifications_enabled": all_data.get(
            "telegram_notifications_enabled", "true"
        ),
        "notifications_enabled": all_data.get("notifications_enabled", "true"),
    }


def get_notification_settings(db: Session) -> dict:
    all_data = get_settings_for_admin(db)
    result = {
        "notifications_enabled": all_data.get("notifications_enabled", "true"),
        "telegram_notifications_enabled": all_data.get(
            "telegram_notifications_enabled", "true"
        ),
    }
    for event in NOTIFICATION_EVENTS:
        result[f"notify_{event}"] = all_data.get(f"notify_{event}", "true")
    return result


def update_settings(db: Session, payload: dict) -> dict:
    for key, value in payload.items():
        if key not in DEFAULT_SETTINGS:
            continue
        if key == "telegram_bot_token" and value in ("", "••••••••"):
            continue
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        str_value = str(value) if value is not None else ""
        if row:
            row.value = str_value
        else:
            db.add(SystemSetting(key=key, value=str_value))
    db.commit()
    return get_settings_for_admin(db)


def update_telegram_settings(db: Session, payload: dict) -> dict:
    filtered = {k: v for k, v in payload.items() if k in TELEGRAM_KEYS}
    update_settings(db, filtered)
    return get_telegram_settings(db)


def update_notification_settings(db: Session, payload: dict) -> dict:
    filtered = {k: v for k, v in payload.items() if k in NOTIFICATION_KEYS}
    update_settings(db, filtered)
    return get_notification_settings(db)


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    return "••••••••" if len(value) > 4 else "****"
