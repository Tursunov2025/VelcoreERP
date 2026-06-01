from sqlalchemy.orm import Session

from services.settings_store import get_settings_for_admin
from services.telegram import send_telegram_message, send_telegram_to_chat


def _is_enabled(settings: dict, key: str) -> bool:
    return str(settings.get(key, "true")).lower() in ("true", "1", "yes")


async def notify_operator_event(
    db: Session,
    event_key: str,
    message: str,
    telegram_id: str | None,
) -> bool:
    """Send Telegram notification to a single operator (no global chat)."""
    if not telegram_id:
        return False

    settings = get_settings_for_admin(db)

    if not _is_enabled(settings, "notifications_enabled"):
        return False
    if not _is_enabled(settings, "telegram_notifications_enabled"):
        return False
    if not _is_enabled(settings, f"notify_{event_key}"):
        return False

    return await send_telegram_to_chat(message, telegram_id, db=db)


async def notify_event(
    db: Session,
    event_key: str,
    message: str,
    *,
    telegram_id: str | None = None,
) -> bool:
    """Send Telegram notification if global toggles allow this event."""
    settings = get_settings_for_admin(db)

    if not _is_enabled(settings, "notifications_enabled"):
        return False
    if not _is_enabled(settings, "telegram_notifications_enabled"):
        return False
    if not _is_enabled(settings, f"notify_{event_key}"):
        return False

    sent = await send_telegram_message(message, db=db)
    if telegram_id:
        sent = await send_telegram_to_chat(message, telegram_id, db=db) or sent
    return sent
