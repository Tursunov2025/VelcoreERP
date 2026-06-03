"""MES BOM line helpers."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from models import MesBomLine, MesProductPart, MesProductTemplate
from routers.uploads_router import UPLOAD_DIR, _resolve_content_type, _safe_ext

MES_BOM_DRAWING_DIR = UPLOAD_DIR / "mes" / "bom"
MES_BOM_DRAWING_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_BOM_DRAWING_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf"}


def active_bom_lines(template: MesProductTemplate) -> list[MesBomLine]:
    lines = template.bom_lines or []
    return sorted(
        [line for line in lines if line.is_active and line.deleted_at is None],
        key=lambda line: (line.sort_order, line.id),
    )


def bom_summary(lines: list[MesBomLine]) -> dict[str, float | int]:
    return {
        "parts_count": len(lines),
        "total_required_quantity": sum(float(line.required_quantity or 0) for line in lines),
        "total_produced_quantity": sum(float(line.produced_quantity or 0) for line in lines),
        "total_accepted_quantity": sum(float(line.accepted_quantity or 0) for line in lines),
        "total_rejected_quantity": sum(float(line.rejected_quantity or 0) for line in lines),
    }


def serialize_bom_line(line: MesBomLine) -> dict:
    part = line.part
    return {
        "id": line.id,
        "template_id": line.template_id,
        "part_id": line.part_id,
        "part_number": part.part_number if part else None,
        "part_name": part.name if part else None,
        "part_unit": part.unit if part else line.unit,
        "part_is_active": bool(part.is_active) if part else False,
        "part_deleted": part.deleted_at is not None if part else True,
        "required_quantity": float(line.required_quantity or 0),
        "produced_quantity": float(line.produced_quantity or 0),
        "accepted_quantity": float(line.accepted_quantity or 0),
        "rejected_quantity": float(line.rejected_quantity or 0),
        "notes": line.notes or "",
        "drawing_url": line.drawing_url,
        "sort_order": line.sort_order,
        "is_active": bool(line.is_active),
        "created_at": line.created_at,
    }


def serialize_bom(template: MesProductTemplate) -> dict:
    lines = active_bom_lines(template)
    return {
        "lines": [serialize_bom_line(line) for line in lines],
        "summary": bom_summary(lines),
    }


def validate_required_quantity(value: float) -> None:
    if value is None or float(value) <= 0:
        raise ValueError("required_quantity must be greater than 0")


def get_active_part(db: Session, part_id: int) -> MesProductPart:
    part = (
        db.query(MesProductPart)
        .filter(
            MesProductPart.id == part_id,
            MesProductPart.is_active.is_(True),
            MesProductPart.deleted_at.is_(None),
        )
        .first()
    )
    if not part:
        raise ValueError("Part not found or inactive")
    return part


def next_sort_order(db: Session, template_id: int) -> int:
    last = (
        db.query(MesBomLine)
        .filter(
            MesBomLine.template_id == template_id,
            MesBomLine.is_active.is_(True),
            MesBomLine.deleted_at.is_(None),
        )
        .order_by(MesBomLine.sort_order.desc(), MesBomLine.id.desc())
        .first()
    )
    if not last:
        return 0
    return int(last.sort_order or 0) + 1


def find_bom_line(
    db: Session, template_id: int, line_id: int, *, active_only: bool = True
) -> MesBomLine | None:
    from sqlalchemy.orm import joinedload

    query = (
        db.query(MesBomLine)
        .options(joinedload(MesBomLine.part))
        .filter(
            MesBomLine.id == line_id,
            MesBomLine.template_id == template_id,
        )
    )
    if active_only:
        query = query.filter(
            MesBomLine.is_active.is_(True),
            MesBomLine.deleted_at.is_(None),
        )
    return query.first()


def save_bom_drawing(content: bytes, original_name: str | None) -> dict:
    ext = _safe_ext(original_name)
    if ext not in ALLOWED_BOM_DRAWING_EXT:
        raise ValueError("Invalid drawing type; allowed: PNG, JPG, WEBP, GIF, PDF")
    stored_name = f"{uuid.uuid4().hex}{ext}"
    filepath = MES_BOM_DRAWING_DIR / stored_name
    filepath.write_bytes(content)
    return {
        "url": f"/uploads/mes/bom/{stored_name}",
        "filename": stored_name,
        "original_filename": original_name or stored_name,
        "content_type": _resolve_content_type(None, original_name),
    }
