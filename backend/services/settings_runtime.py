"""Runtime helpers — read configurable values from settings cache with code fallbacks."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from constants import (
    DEPARTMENTS,
    MES_DEFAULT_PRODUCTION_STAGES,
    PRODUCTION_STAGES,
)
from services.materials_warehouse import DEFAULT_CATEGORIES
from services.settings_cache import get_cached_json_list, get_cached_setting, is_cached_truthy

DEFAULT_CONSUMPTION_STAGES = ("Lazer", "Kraska")


def get_company_name(db: Session | None = None) -> str:
    return get_cached_setting("company_name", "Velcore ERP", db) or "Velcore ERP"


def get_production_stages(db: Session | None = None) -> list[str]:
    stages = get_cached_json_list("production_stages_json", None, db)
    if stages and all(isinstance(s, str) for s in stages):
        return stages
    return list(PRODUCTION_STAGES)


def get_departments(db: Session | None = None) -> list[str]:
    depts = get_cached_json_list("departments_json", None, db)
    if depts and all(isinstance(d, str) for d in depts):
        return depts
    return list(DEPARTMENTS)


def get_mes_default_stages(db: Session | None = None) -> list[tuple[str, str]]:
    raw = get_cached_setting("mes_default_stages_json", None, db)
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                result = []
                for item in parsed:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        result.append((str(item[0]), str(item[1])))
                    elif isinstance(item, dict) and item.get("name"):
                        result.append((str(item["name"]), str(item.get("department", "Admin"))))
                if result:
                    return result
        except json.JSONDecodeError:
            pass
    return list(MES_DEFAULT_PRODUCTION_STAGES)


def get_material_categories_seed(db: Session | None = None) -> list[tuple[str, str]]:
    raw = get_cached_setting("materials_categories_json", None, db)
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                result = []
                for item in parsed:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        result.append((str(item[0]), str(item[1])))
                    elif isinstance(item, dict) and item.get("code") and item.get("name"):
                        result.append((str(item["code"]), str(item["name"])))
                if result:
                    return result
        except json.JSONDecodeError:
            pass
    return list(DEFAULT_CATEGORIES)


def get_auto_consume_stages(db: Session | None = None) -> tuple[str, ...]:
    stages = get_cached_json_list("materials_auto_consume_stages_json", None, db)
    if stages and all(isinstance(s, str) for s in stages):
        return tuple(stages)
    return DEFAULT_CONSUMPTION_STAGES


def is_auto_consume_enabled(db: Session | None = None) -> bool:
    return is_cached_truthy("materials_auto_consume_enabled", True, db)


def get_costing_currency_symbol(db: Session | None = None) -> str:
    return get_cached_setting("costing_currency_symbol", "so'm", db) or "so'm"


def is_job_material_cost_tracking_enabled(db: Session | None = None) -> bool:
    return is_cached_truthy("costing_track_job_material_cost", True, db)
