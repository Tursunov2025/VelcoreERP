"""Shared safety helpers for Platform Administration."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from models import AuditLog, SystemSetting

SENSITIVE_KEYS = re.compile(r"password|secret|token|authorization|api[_-]?key|connection[_-]?string", re.I)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): ("[REDACTED]" if SENSITIVE_KEYS.search(str(key)) else redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def append_audit(
    db: Session,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    module: str = "platform_administration",
    result: str = "success",
    details: Any = None,
    ip_address: str = "",
    correlation_id: str = "",
) -> None:
    payload = {
        "module": module,
        "result": result,
        "ip_address": ip_address,
        "correlation_id": correlation_id,
        "details": redact(details or {}),
    }
    db.add(AuditLog(username=actor, action=action, entity_type=entity_type, entity_id=entity_id, details=json.dumps(payload, ensure_ascii=False, default=str)))


def get_versioned_setting(db: Session, key: str, defaults: dict[str, Any]) -> dict[str, Any]:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not row:
        return {**defaults, "version": 0}
    try:
        value = json.loads(row.value)
    except (TypeError, json.JSONDecodeError):
        value = {}
    return {**defaults, **value, "version": int(value.get("version", 0))}


def put_versioned_setting(db: Session, key: str, payload: dict[str, Any], expected_version: int) -> dict[str, Any]:
    current = get_versioned_setting(db, key, {})
    if current["version"] != expected_version:
        raise ValueError("Configuration changed by another administrator; reload and try again")
    result = {**payload, "version": expected_version + 1}
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        row.value = json.dumps(result, ensure_ascii=False)
    else:
        db.add(SystemSetting(key=key, value=json.dumps(result, ensure_ascii=False)))
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
