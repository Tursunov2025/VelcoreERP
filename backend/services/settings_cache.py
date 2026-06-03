"""In-memory settings cache for live reads without per-request DB hits."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from sqlalchemy.orm import Session

_lock = threading.Lock()
_cache: dict[str, str] = {}
_loaded_at: float = 0.0
CACHE_TTL_SECONDS = 15


def invalidate_settings_cache() -> None:
    with _lock:
        global _cache, _loaded_at
        _cache = {}
        _loaded_at = 0.0


def refresh_settings_cache(db: Session) -> dict[str, str]:
    from services.settings_store import get_settings_for_admin

    with _lock:
        global _cache, _loaded_at
        _cache = get_settings_for_admin(db)
        _loaded_at = time.time()
        return dict(_cache)


def _ensure_fresh(db: Session | None) -> dict[str, str]:
    global _cache, _loaded_at
    now = time.time()
    with _lock:
        if _cache and now - _loaded_at < CACHE_TTL_SECONDS:
            return dict(_cache)
    if db is None:
        with _lock:
            return dict(_cache)
    return refresh_settings_cache(db)


def get_cached_setting(key: str, default: str | None = None, db: Session | None = None) -> str | None:
    data = _ensure_fresh(db)
    if key in data:
        return data[key]
    from services.settings_store import DEFAULT_SETTINGS

    return DEFAULT_SETTINGS.get(key, default)


def get_cached_int(key: str, default: int, db: Session | None = None) -> int:
    raw = get_cached_setting(key, str(default), db)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def get_cached_float(key: str, default: float, db: Session | None = None) -> float:
    raw = get_cached_setting(key, str(default), db)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def is_cached_truthy(key: str, default: bool = True, db: Session | None = None) -> bool:
    raw = (get_cached_setting(key, "true" if default else "false", db) or "").lower()
    return raw in {"true", "1", "yes", "on"}


def get_cached_json(key: str, default: Any = None, db: Session | None = None) -> Any:
    raw = get_cached_setting(key, None, db)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def get_cached_json_list(key: str, default: list | None = None, db: Session | None = None) -> list:
    value = get_cached_json(key, default or [], db)
    return value if isinstance(value, list) else (default or [])
