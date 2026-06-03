"""Super Admin UI config: menu visibility, dashboard widgets, mobile app."""

from __future__ import annotations

import json
from typing import Any

from constants import DEPARTMENTS, PRODUCTION_STAGES

# Mirrors frontend NAV_ITEMS iconKey + path (settings-controlled visibility).
DEFAULT_NAV_VISIBILITY: dict[str, bool] = {
    "dashboard": True,
    "production": True,
    "orders": True,
    "warehouse": True,
    "shipping": True,
    "chat": True,
    "tasks": True,
    "llp": True,
    "mes": True,
    "materials": True,
    "lazerTerminal": True,
    "svarshikTerminal": True,
    "kraskaTerminal": True,
    "qcTerminal": True,
    "packagingTerminal": True,
    "warehouseTerminal": True,
    "dispatchTerminal": True,
    "operators": True,
    "analytics": True,
    "finance": True,
    "invoices": True,
    "controlCenter": True,
    "settings": True,
}

DEFAULT_DASHBOARD_WIDGETS: list[dict[str, Any]] = [
    {"id": "order_stats", "enabled": True, "order": 1},
    {"id": "clock", "enabled": True, "order": 2},
    {"id": "online_operators", "enabled": True, "order": 3},
    {"id": "production_chart", "enabled": True, "order": 4},
    {"id": "delayed_summary", "enabled": True, "order": 5},
]

DEFAULT_MOBILE_APP: dict[str, Any] = {
    "app_name": "Azmus CRM",
    "android_package": "com.azmus.crm",
    "min_version": "1.0.0",
    "latest_version": "1.0.0",
    "force_update": False,
    "apk_url": "",
    "release_notes": "",
    "maintenance_mode": False,
    "maintenance_message": "",
}


def _parse_json_object(raw: str | None, default: dict) -> dict:
    if not raw:
        return dict(default)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            merged = dict(default)
            merged.update({k: bool(v) for k, v in data.items()})
            return merged
    except (json.JSONDecodeError, TypeError):
        pass
    return dict(default)


def _parse_json_list(raw: str | None, default: list) -> list:
    if not raw:
        return list(default)
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return list(default)


def get_nav_visibility(settings: dict[str, str]) -> dict[str, bool]:
    return _parse_json_object(settings.get("nav_visibility_json"), DEFAULT_NAV_VISIBILITY)


def get_dashboard_widgets(settings: dict[str, str]) -> list[dict[str, Any]]:
    widgets = _parse_json_list(settings.get("dashboard_widgets_json"), DEFAULT_DASHBOARD_WIDGETS)
    return sorted(
        [w for w in widgets if isinstance(w, dict) and w.get("id")],
        key=lambda w: int(w.get("order", 99)),
    )


def get_mobile_app_config(settings: dict[str, str]) -> dict[str, Any]:
    raw = settings.get("mobile_app_json")
    if not raw:
        return dict(DEFAULT_MOBILE_APP)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            merged = dict(DEFAULT_MOBILE_APP)
            merged.update(data)
            return merged
    except (json.JSONDecodeError, TypeError):
        pass
    return dict(DEFAULT_MOBILE_APP)


def serialize_nav_visibility(visibility: dict[str, bool]) -> str:
    merged = dict(DEFAULT_NAV_VISIBILITY)
    merged.update(visibility)
    return json.dumps(merged, ensure_ascii=False)


def serialize_dashboard_widgets(widgets: list[dict]) -> str:
    return json.dumps(widgets, ensure_ascii=False)


def serialize_mobile_app(config: dict) -> str:
    merged = dict(DEFAULT_MOBILE_APP)
    merged.update(config)
    return json.dumps(merged, ensure_ascii=False)


def filter_nav_by_visibility(
    icon_key: str | None,
    visibility: dict[str, bool],
) -> bool:
    if not icon_key:
        return True
    return visibility.get(icon_key, DEFAULT_NAV_VISIBILITY.get(icon_key, True))
