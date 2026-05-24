from typing import Optional

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
