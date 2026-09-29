"""Shared Velkore corporate document design primitives.

This module is intentionally business-entity agnostic. Export builders reuse the
same palette, typography, localization and branding resolution instead of
inventing per-endpoint styles.
"""

from __future__ import annotations

import io
import os
from datetime import date, datetime
from typing import Any

from services.branding import get_branding

NAVY = "172B4D"
BLUE = "2563EB"
GREEN = "15803D"
AMBER = "B45309"
RED = "B91C1C"
SLATE = "475569"
PALE = "F1F5F9"
BORDER = "CBD5E1"
WHITE = "FFFFFF"

STATUS_LABELS = {
    "uz": {
        "created": "Yaratilgan", "pending": "Kutilmoqda", "packed": "Qadoqlangan",
        "received": "Omborga qabul qilingan", "in_warehouse": "Omborda",
        "placed": "Joylashtirilgan", "loaded": "Yuklangan", "shipped": "Jo‘natilgan",
        "dispatched": "Jo‘natilgan", "in_transit": "Yo‘lda", "delivered": "Yetkazilgan",
        "accepted": "Qabul qilingan", "finished": "Tayyor", "completed": "Yakunlangan",
        "open": "Ochiq", "resolved": "Hal qilingan", "closed": "Yopilgan",
        "qc_pass": "Sifat nazoratidan o‘tdi", "qc_fail": "Sifat nazoratidan o‘tmadi",
        "rework_completed": "Qayta ishlash yakunlandi", "rework": "Qayta ishlash",
    },
    "ru": {
        "created": "Создан", "pending": "Ожидает", "packed": "Упакован",
        "received": "Принят на склад", "in_warehouse": "На складе", "placed": "Размещён",
        "loaded": "Загружен", "shipped": "Отправлен", "dispatched": "Отправлен",
        "in_transit": "В пути", "delivered": "Доставлен", "accepted": "Принят",
        "finished": "Готов", "completed": "Завершён", "open": "Открыт",
        "resolved": "Решён", "closed": "Закрыт", "qc_pass": "Контроль пройден",
        "qc_fail": "Контроль не пройден", "rework_completed": "Доработка завершена",
        "rework": "Доработка",
    },
}

STAGE_LABELS = {
    "uz": {"lazer": "Lazer", "laser": "Lazer", "svarshik": "Svarka", "svarka": "Svarka", "kraska": "Bo‘yash", "painting": "Bo‘yash", "tekshiruv": "Sifat nazorati", "qc": "Sifat nazorati", "upakovka": "Qadoqlash", "packaging": "Qadoqlash", "sklad": "Ombor", "warehouse": "Ombor", "yuklash": "Yuklash", "loading": "Yuklash", "dispatch": "Jo‘natish", "qc / rework": "QC / Qayta ishlash"},
    "ru": {"lazer": "Лазер", "laser": "Лазер", "svarshik": "Сварка", "svarka": "Сварка", "kraska": "Покраска", "painting": "Покраска", "tekshiruv": "Контроль качества", "qc": "Контроль качества", "upakovka": "Упаковка", "packaging": "Упаковка", "sklad": "Склад", "warehouse": "Склад", "yuklash": "Погрузка", "loading": "Погрузка", "dispatch": "Отправка", "qc / rework": "QC / Доработка"},
}


def language(value: str | None) -> str:
    return "ru" if str(value or "").lower().startswith("ru") else "uz"


def status_label(value: Any, lang: str = "uz") -> str:
    if value in (None, ""):
        return "—"
    key = str(value).strip().lower()
    return STATUS_LABELS[language(lang)].get(key, key.replace("_", " ").capitalize())


def stage_label(value: Any, lang: str = "uz") -> str:
    if value in (None, ""):
        return "—"
    key = str(value).strip().lower()
    return STAGE_LABELS[language(lang)].get(key, str(value))


def format_datetime(value: Any, lang: str = "uz") -> str:
    if not value:
        return "—"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if isinstance(value, (datetime, date)):
        return value.strftime("%d.%m.%Y %H:%M" if isinstance(value, datetime) else "%d.%m.%Y")
    return str(value)


def duration_label(seconds: Any, lang: str = "uz") -> str:
    if seconds in (None, ""):
        return "—"
    minutes = max(0, round(float(seconds) / 60))
    return f"{minutes} {'daq.' if language(lang) == 'uz' else 'мин.'}"


def corporate_branding(db) -> dict[str, str]:
    branding = get_branding(db)
    return {
        "name": branding.get("app_name") or "Velkore ERP",
        "tagline": branding.get("tagline") or "Industrial ERP",
        "primary": str(branding.get("color_primary") or "#172B4D").lstrip("#")[:6].upper(),
        "logo": _safe_logo_path(branding.get("logo_main") or branding.get("logo_sidebar")),
    }


def _safe_logo_path(value: Any) -> str:
    path = str(value or "").strip()
    if not path or path.startswith(("http://", "https://", "data:")):
        return ""
    candidate = os.path.abspath(path)
    return candidate if os.path.isfile(candidate) else ""


def qr_png(payload: str, *, pixels: int = 360) -> bytes:
    import qrcode

    image = qrcode.make(payload or "").convert("RGB").resize((pixels, pixels))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def result_color(value: Any) -> str:
    key = str(value or "").lower()
    if "fail" in key or "reject" in key:
        return RED
    if "warning" in key or "pending" in key or "rework" in key:
        return AMBER
    if "pass" in key or "accept" in key or "complete" in key or "deliver" in key:
        return GREEN
    return BLUE
