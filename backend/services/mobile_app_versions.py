"""Mobile app version publishing and latest-version lookup."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from models import MobileAppVersion
from services.control_center_config import DEFAULT_MOBILE_APP, serialize_mobile_app
from services.settings_store import update_settings_group


def version_to_dict(row: MobileAppVersion) -> dict[str, Any]:
    return {
        "id": row.id,
        "version_name": row.version_name,
        "version_code": row.version_code,
        "apk_url": row.apk_url or "",
        "release_notes": row.release_notes or "",
        "force_update": bool(row.force_update),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def version_public_payload(row: MobileAppVersion) -> dict[str, Any]:
    return {
        "latest_version": row.version_name,
        "version_code": row.version_code,
        "apk_url": row.apk_url or "",
        "force_update": bool(row.force_update),
        "release_notes": row.release_notes or "",
    }


def get_latest_version(db: Session) -> MobileAppVersion | None:
    return (
        db.query(MobileAppVersion)
        .order_by(desc(MobileAppVersion.version_code), desc(MobileAppVersion.id))
        .first()
    )


def list_versions(db: Session, limit: int = 50) -> list[MobileAppVersion]:
    return (
        db.query(MobileAppVersion)
        .order_by(desc(MobileAppVersion.version_code), desc(MobileAppVersion.id))
        .limit(limit)
        .all()
    )


def _sync_executive_mobile_json(db: Session, row: MobileAppVersion) -> None:
    payload = {
        **DEFAULT_MOBILE_APP,
        "latest_version": row.version_name,
        "min_version": row.version_name,
        "apk_url": row.apk_url or "",
        "release_notes": row.release_notes or "",
        "force_update": bool(row.force_update),
    }
    update_settings_group(
        db,
        "executive",
        {"mobile_app_json": serialize_mobile_app(payload)},
    )


def publish_version(
    db: Session,
    *,
    version_name: str,
    version_code: int,
    apk_url: str,
    release_notes: str = "",
    force_update: bool = False,
) -> MobileAppVersion:
    name = (version_name or "").strip()
    url = (apk_url or "").strip()
    if not name:
        raise ValueError("version_name is required")
    if version_code < 1:
        raise ValueError("version_code must be >= 1")
    if not url:
        raise ValueError("apk_url is required")

    latest = get_latest_version(db)
    if latest and version_code < latest.version_code:
        raise ValueError(
            f"version_code must be >= {latest.version_code} (current latest)"
        )

    if latest and latest.version_code == version_code:
        latest.version_name = name
        latest.apk_url = url
        latest.release_notes = release_notes or ""
        latest.force_update = bool(force_update)
        db.commit()
        db.refresh(latest)
        row = latest
    else:
        row = MobileAppVersion(
            version_name=name,
            version_code=version_code,
            apk_url=url,
            release_notes=release_notes or "",
            force_update=bool(force_update),
        )
        db.add(row)
        db.commit()
        db.refresh(row)

    _sync_executive_mobile_json(db, row)
    return row


def ensure_default_version(db: Session) -> MobileAppVersion | None:
    if get_latest_version(db):
        return get_latest_version(db)
    row = MobileAppVersion(
        version_name="1.0.0",
        version_code=1,
        apk_url="",
        release_notes="Initial release",
        force_update=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
