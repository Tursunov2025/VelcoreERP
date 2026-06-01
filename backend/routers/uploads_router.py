import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from auth.deps import get_current_user, require_admin
from models import User

logger = logging.getLogger("azmus.uploads")

router = APIRouter(prefix="/uploads", tags=["uploads"])

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(_BACKEND_ROOT / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
BRANDING_DIR = UPLOAD_DIR / "branding"
BRANDING_DIR.mkdir(parents=True, exist_ok=True)

# Extension → canonical MIME (used when browser sends empty/wrong Content-Type)
EXT_MIME = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".txt": "text/plain",
}

ALLOWED_EXTENSIONS = set(EXT_MIME.keys())

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/svg+xml",
    "image/x-icon",
}

ALLOWED_FILE_TYPES = ALLOWED_IMAGE_TYPES | set(EXT_MIME.values()) | {
    "text/plain",
    "application/octet-stream",
    "application/zip",  # some browsers send docx/xlsx as zip
    "application/x-zip-compressed",
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_FILE_SIZE = 10 * 1024 * 1024


def _safe_ext(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return Path(filename).suffix.lower()


def _resolve_content_type(content_type: str | None, filename: str | None) -> str:
    ext = _safe_ext(filename)
    ct = (content_type or "").split(";")[0].strip().lower()

    if ct in ALLOWED_FILE_TYPES:
        # zip is only OK for office formats
        if ct in ("application/zip", "application/x-zip-compressed"):
            if ext in (".docx", ".xlsx"):
                return EXT_MIME[ext]
            return ct
        return ct

    if ext in EXT_MIME:
        return EXT_MIME[ext]

    return ct


def _is_allowed(content_type: str | None, filename: str | None) -> bool:
    ext = _safe_ext(filename)
    if ext in ALLOWED_EXTENSIONS:
        return True
    resolved = _resolve_content_type(content_type, filename)
    return resolved in ALLOWED_FILE_TYPES


def _save_upload(content: bytes, original_name: str | None, *, subdir: str | None = None) -> dict:
    ext = _safe_ext(original_name) or ".bin"
    if ext not in ALLOWED_EXTENSIONS and ext != ".bin":
        ext = ".bin"
    stored_name = f"{uuid.uuid4().hex}{ext}"
    target_dir = UPLOAD_DIR / subdir if subdir else UPLOAD_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    filepath = target_dir / stored_name
    filepath.write_bytes(content)
    logger.info(
        "saved upload original=%s stored=%s path=%s bytes=%d",
        original_name,
        stored_name,
        filepath,
        len(content),
    )
    url_path = f"/uploads/{subdir}/{stored_name}" if subdir else f"/uploads/{stored_name}"
    return {
        "url": url_path,
        "filename": stored_name,
        "original_filename": original_name or stored_name,
        "content_type": _resolve_content_type(None, original_name),
    }


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
):
    resolved = _resolve_content_type(file.content_type, file.filename)
    if resolved not in ALLOWED_IMAGE_TYPES and _safe_ext(file.filename) not in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
    }:
        raise HTTPException(status_code=400, detail="Invalid image type")

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    result = _save_upload(content, file.filename)
    result["content_type"] = resolved or result["content_type"]
    return result


@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    logger.info(
        "upload request user=%s name=%s content_type=%s",
        user.username,
        file.filename,
        file.content_type,
    )

    if not _is_allowed(file.content_type, file.filename):
        logger.warning(
            "rejected upload name=%s content_type=%s ext=%s",
            file.filename,
            file.content_type,
            _safe_ext(file.filename),
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.filename} ({file.content_type or 'unknown'})",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    resolved = _resolve_content_type(file.content_type, file.filename)
    result = _save_upload(content, file.filename)
    result["content_type"] = resolved
    logger.info("upload ok user=%s url=%s", user.username, result["url"])
    return result


@router.post("/branding")
async def upload_branding_asset(
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
):
    resolved = _resolve_content_type(file.content_type, file.filename)
    allowed_ext = _safe_ext(file.filename) in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".svg",
        ".ico",
    }
    if resolved not in ALLOWED_IMAGE_TYPES and not allowed_ext:
        raise HTTPException(status_code=400, detail="Invalid branding image type")

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    result = _save_upload(content, file.filename, subdir="branding")
    result["content_type"] = resolved or result["content_type"]
    return result
