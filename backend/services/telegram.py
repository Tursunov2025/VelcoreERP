import os

import httpx

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


async def send_telegram_message(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                url,
                json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            )
            return response.status_code == 200
    except Exception:
        return False


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
