"""Material image upload helpers."""

from __future__ import annotations

import uuid

from routers.uploads_router import (
    UPLOAD_DIR,
    _resolve_content_type,
    _safe_ext,
)

MATERIAL_IMAGE_DIR = UPLOAD_DIR / "mes" / "materials"
MATERIAL_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MATERIAL_IMAGE_EXT = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
}


def save_material_image(content: bytes, original_name: str | None) -> dict:
    ext = _safe_ext(original_name)

    if ext not in ALLOWED_MATERIAL_IMAGE_EXT:
        raise ValueError("Invalid image type; allowed: PNG, JPG, WEBP, GIF")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    filepath = MATERIAL_IMAGE_DIR / stored_name
    filepath.write_bytes(content)

    return {
        "url": f"/uploads/mes/materials/{stored_name}",
        "filename": stored_name,
        "original_filename": original_name or stored_name,
        "content_type": _resolve_content_type(None, original_name),
    }
