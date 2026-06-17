import logging

import httpx
from sqlalchemy.orm import Session

from services.settings_store import get_settings_for_admin

logger = logging.getLogger("azmus.telegram")


def _config(db: Session | None) -> tuple[str, str]:
    if db is not None:
        settings = get_settings_for_admin(db)
        token = settings.get("telegram_bot_token") or ""
        chat_id = settings.get("telegram_chat_id") or ""
        if token and chat_id:
            return token, chat_id

    import os

    return os.getenv("TELEGRAM_BOT_TOKEN", ""), os.getenv("TELEGRAM_CHAT_ID", "")


async def send_telegram_to_chat(text: str, chat_id: str, db: Session | None = None) -> bool:
    token, _ = _config(db)
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                url,
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
            ok = response.status_code == 200
            if not ok:
                logger.warning("telegram send failed chat=%s status=%s", chat_id, response.status_code)
            return ok
    except Exception as exc:
        logger.warning("telegram error chat=%s err=%s", chat_id, exc)
        return False


async def send_telegram_message(
    text: str,
    db: Session | None = None,
    chat_id: str | None = None,
) -> bool:
    token, default_chat = _config(db)
    target = chat_id or default_chat
    if not token or not target:
        return False
    return await send_telegram_to_chat(text, target, db=db)


async def send_test_message(db: Session) -> dict:
    token, chat_id = _config(db)
    if not token:
        return {"ok": False, "error": "Bot token not configured"}
    if not chat_id:
        return {"ok": False, "error": "Chat ID not configured"}

    text = "✅ <b>Velcore ERP</b>\nTelegram test xabari muvaffaqiyatli yuborildi."
    ok = await send_telegram_message(text, db=db)
    return {"ok": ok, "error": None if ok else "Telegram API rejected the message"}


def format_new_order_alert(order) -> str:
    return (
        f"🆕 <b>Yangi zakaz #{order.id}</b>\n"
        f"Mijoz: {order.client}\n"
        f"Telefon: {order.phone or '-'}\n"
        f"Summa: {order.amount} so'm\n"
        f"Holat: {order.status}"
    )


def format_ready_order_alert(order) -> str:
    return (
        f"✅ <b>Zakaz tayyor #{order.id}</b>\n"
        f"Mijoz: {order.client}\n"
        f"Summa: {order.amount} so'm"
    )


def format_new_task_assignment_alert(task, operator_name: str) -> str:
    import os

    priority_labels = {
        "normal": "Oddiy",
        "important": "Muhim",
        "urgent": "Shoshilinch",
    }
    deadline = "-"
    if task.deadline:
        deadline = task.deadline.strftime("%d.%m.%Y %H:%M")
    priority = priority_labels.get(task.priority, task.priority or "-")

    app_url = os.getenv("APP_URL", "").strip().rstrip("/")
    if app_url:
        open_line = f'\n\n<a href="{app_url}/tasks">Open task inside ERP.</a>'
    else:
        open_line = "\n\nOpen task inside ERP."

    return (
        f"📋 <b>Yangi vazifa</b>\n\n"
        f"Nomi: {task.title}\n"
        f"Muhimlik: {priority}\n"
        f"Muddat: {deadline}\n"
        f"Mas'ul: {operator_name}"
        f"{open_line}"
    )


def format_overdue_task_reminder(task) -> str:
    deadline = "-"
    if task.deadline:
        deadline = task.deadline.strftime("%d.%m.%Y %H:%M")
    return (
        f"⚠️ <b>Vazifa muddati o'tgan</b>\n\n"
        f"Nomi: {task.title}\n"
        f"Muddat: {deadline}\n\n"
        f"Iltimos vazifani yakunlang."
    )


def format_task_status_alert(task, operator: str, status: str) -> str:
    return (
        f"🔄 <b>Vazifa #{task.id}</b>\n"
        f"{task.title}\n"
        f"Operator: {operator}\n"
        f"Holat: {status}"
    )


def format_shipment_alert(group) -> str:
    return (
        f"🚚 <b>Yuk chiqarildi #{group.id}</b>\n"
        f"Manzil: {group.destination or '-'}\n"
        f"Mahsulot: {group.total_products_count} ta"
    )


def format_warehouse_movement_alert(material, movement, operator: str) -> str:
    direction = "Kirim" if movement.movement_type == "in" else "Chiqim"
    return (
        f"📦 <b>Ombor: {direction}</b>\n"
        f"Material: {material.name}\n"
        f"Miqdor: {movement.quantity}\n"
        f"Operator: {operator}"
    )


def format_chat_alert(room_name: str, sender: str, preview: str) -> str:
    return f"💬 <b>{room_name}</b>\n{sender}: {preview[:120]}"


def format_llp_important_alert(document, uploaded_by: str) -> str:
    folder = document.folder.name if document.folder else "—"
    return (
        f"📁 <b>Muhim hujjat yuklandi</b>\n\n"
        f"Sarlavha: {document.title}\n"
        f"Jild: {folder}\n"
        f"Fayl: {document.original_filename or document.filename}\n"
        f"Yuklagan: {uploaded_by}"
    )


def _driver_line(driver) -> str:
    if not driver:
        return "—"
    name = getattr(driver, "full_name", None) or str(driver)
    phone = getattr(driver, "phone", "") or ""
    return f"{name}" + (f" ({phone})" if phone else "")


def format_gps_offline_alert(plate: str, driver, offline_minutes: int, destination: str) -> str:
    return (
        f"📴 <b>GPS offline</b>\n"
        f"Vehicle: {plate}\n"
        f"Driver: {_driver_line(driver)}\n"
        f"No signal for {offline_minutes} min\n"
        f"Destination: {destination or '—'}"
    )


def format_gps_destination_alert(plate: str, driver, city: str, destination: str) -> str:
    return (
        f"🏙 <b>Arrived at destination area</b>\n"
        f"Vehicle: {plate}\n"
        f"Driver: {_driver_line(driver)}\n"
        f"Current city: {city}\n"
        f"Trip destination: {destination}"
    )


def format_gps_border_alert(
    plate: str, driver, from_country: str, to_country: str, location: str
) -> str:
    return (
        f"🛃 <b>Border crossing</b>\n"
        f"Vehicle: {plate}\n"
        f"Driver: {_driver_line(driver)}\n"
        f"{from_country} → {to_country}\n"
        f"Near: {location or '—'}"
    )
