"""MES product drawing helpers."""

from __future__ import annotations

import uuid

from models import MesProductDrawing, MesProductTemplate
from routers.uploads_router import UPLOAD_DIR, _resolve_content_type, _safe_ext

MES_DRAWING_DIR = UPLOAD_DIR / "mes" / "drawings"
MES_DRAWING_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_DRAWING_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".pdf"}
MAX_DRAWING_SIZE = 10 * 1024 * 1024


def active_drawings(template: MesProductTemplate) -> list[MesProductDrawing]:
    drawings = template.drawings or []
    return sorted(
        [d for d in drawings if d.is_active and d.deleted_at is None],
        key=lambda d: (-int(d.is_primary), d.created_at or d.id, d.id),
    )


def serialize_drawing(drawing: MesProductDrawing) -> dict:
    return {
        "id": drawing.id,
        "template_id": drawing.template_id,
        "title": drawing.title,
        "url": drawing.url,
        "filename": drawing.filename,
        "original_filename": drawing.original_filename,
        "content_type": drawing.content_type,
        "file_size": drawing.file_size,
        "revision": drawing.revision or "A",
        "is_primary": bool(drawing.is_primary),
        "is_active": bool(drawing.is_active),
        "uploaded_by": drawing.uploaded_by,
        "created_at": drawing.created_at,
    }


def serialize_drawings(template: MesProductTemplate) -> dict:
    drawings = active_drawings(template)
    primary = next((d for d in drawings if d.is_primary), None)
    return {
        "drawings": [serialize_drawing(d) for d in drawings],
        "count": len(drawings),
        "primary_drawing_id": primary.id if primary else None,
    }


def save_drawing_file(content: bytes, original_name: str | None) -> dict:
    if len(content) > MAX_DRAWING_SIZE:
        raise ValueError("Drawing too large (max 10MB)")
    ext = _safe_ext(original_name)
    if ext not in ALLOWED_DRAWING_EXT:
        raise ValueError("Invalid drawing type; allowed: PNG, JPG, WEBP, GIF, SVG, PDF")
    stored_name = f"{uuid.uuid4().hex}{ext}"
    filepath = MES_DRAWING_DIR / stored_name
    filepath.write_bytes(content)
    content_type = _resolve_content_type(None, original_name)
    return {
        "url": f"/uploads/mes/drawings/{stored_name}",
        "filename": stored_name,
        "original_filename": original_name or stored_name,
        "content_type": content_type,
        "file_size": len(content),
    }


def clear_primary_drawings(template: MesProductTemplate) -> None:
    for drawing in active_drawings(template):
        drawing.is_primary = False
