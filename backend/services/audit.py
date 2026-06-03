import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from models import AuditLog


def log_action(
    db: Session,
    username: str,
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    details: str = "",
):
    db.add(
        AuditLog(
            username=username,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
    )


def log_value_change(
    db: Session,
    username: str,
    action: str,
    entity_type: str,
    entity_id: Optional[int],
    field: str,
    old_value: Any,
    new_value: Any,
):
    details = json.dumps(
        {"field": field, "old": old_value, "new": new_value},
        ensure_ascii=False,
        default=str,
    )
    log_action(db, username, action, entity_type, entity_id, details)
