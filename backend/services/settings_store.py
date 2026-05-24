import json
import os

from sqlalchemy.orm import Session

from models import SystemSetting

DEFAULT_SETTINGS = {
    "company_name": "Azmus Furniture",
    "company_phone": "",
    "company_logo_url": "",
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "notifications_enabled": "true",
    "jwt_access_minutes": "60",
    "jwt_refresh_days": "7",
    "auto_backup_enabled": "false",
    "auto_backup_interval_hours": "24",
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


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    return "••••••••" if len(value) > 4 else "****"
