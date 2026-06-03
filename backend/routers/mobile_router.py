"""Public mobile update API and admin version management."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from auth.deps import require_admin
from config.paths import UPLOAD_PATH
from database import get_db
from models import User
from schemas import MobileVersionPublish, MobileVersionResponse
from services.mobile_app_versions import (
    get_latest_version,
    list_versions,
    publish_version,
    version_public_payload,
    version_to_dict,
)

router = APIRouter(tags=["mobile"])

MOBILE_APK_DIR = UPLOAD_PATH / "mobile"
MOBILE_APK_DIR.mkdir(parents=True, exist_ok=True)
MAX_APK_BYTES = 150 * 1024 * 1024


def _absolute_apk_url(request: Request, apk_url: str) -> str:
    raw = (apk_url or "").strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    base = str(request.base_url).rstrip("/")
    if raw.startswith("/"):
        return f"{base}{raw}"
    return f"{base}/{raw}"


@router.get("/mobile/version", response_model=MobileVersionResponse)
def get_mobile_version(request: Request, db: Session = Depends(get_db)):
    row = get_latest_version(db)
    if not row or not (row.apk_url or "").strip():
        return MobileVersionResponse(
            latest_version="0.0.0",
            version_code=0,
            apk_url="",
            force_update=False,
            release_notes="",
        )
    payload = version_public_payload(row)
    payload["apk_url"] = _absolute_apk_url(request, payload["apk_url"])
    return MobileVersionResponse(**payload)


@router.get("/admin/mobile/versions")
def admin_list_versions(
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
):
    rows = list_versions(db)
    return {"items": [version_to_dict(r) for r in rows]}


@router.get("/admin/mobile/versions/latest")
def admin_get_latest_version(
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
):
    row = get_latest_version(db)
    if not row:
        return None
    return version_to_dict(row)


@router.put("/admin/mobile/versions/publish")
def admin_publish_version(
    data: MobileVersionPublish,
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
):
    try:
        row = publish_version(
            db,
            version_name=data.version_name,
            version_code=data.version_code,
            apk_url=data.apk_url,
            release_notes=data.release_notes or "",
            force_update=data.force_update,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return version_to_dict(row)


@router.post("/admin/mobile/apk-upload")
async def admin_upload_apk(
    request: Request,
    file: UploadFile = File(...),
    _user: User = Depends(require_admin),
):
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext != ".apk":
        raise HTTPException(status_code=400, detail="Only .apk files are allowed")

    content = await file.read()
    if len(content) > MAX_APK_BYTES:
        raise HTTPException(status_code=400, detail="APK exceeds 150 MB limit")
    if len(content) < 1024:
        raise HTTPException(status_code=400, detail="APK file is too small")

    safe_name = f"azmus-{uuid.uuid4().hex}.apk"
    dest = MOBILE_APK_DIR / safe_name
    dest.write_bytes(content)

    relative = f"/uploads/mobile/{safe_name}"
    public_url = _absolute_apk_url(request, relative)
    return {
        "path": relative,
        "apk_url": public_url,
        "filename": safe_name,
        "size_bytes": len(content),
    }
