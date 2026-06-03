"""MES product template helpers (duplicate, file copy)."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from models import (
    MesBomLine,
    MesProductDrawing,
    MesProductTemplate,
    MesProductionRoute,
    MesRouteStep,
)
from routers.uploads_router import UPLOAD_DIR, _resolve_content_type, _safe_ext

MES_TEMPLATE_IMAGE_DIR = UPLOAD_DIR / "mes" / "templates"
MES_TEMPLATE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_TEMPLATE_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _copy_upload_file(url: str | None) -> str | None:
    if not url or not url.startswith("/uploads/"):
        return None
    rel = url[len("/uploads/") :]
    src = UPLOAD_DIR.joinpath(*rel.split("/"))
    if not src.is_file():
        return None
    ext = src.suffix.lower()
    dest_name = f"{uuid.uuid4().hex}{ext}"
    if "mes/templates" in rel.replace("\\", "/"):
        dest_dir = MES_TEMPLATE_IMAGE_DIR
    elif "mes/drawings" in rel.replace("\\", "/"):
        dest_dir = UPLOAD_DIR / "mes" / "drawings"
        dest_dir.mkdir(parents=True, exist_ok=True)
    elif "mes/bom" in rel.replace("\\", "/"):
        dest_dir = UPLOAD_DIR / "mes" / "bom"
        dest_dir.mkdir(parents=True, exist_ok=True)
    else:
        dest_dir = MES_TEMPLATE_IMAGE_DIR
    dest = dest_dir / dest_name
    shutil.copy2(src, dest)
    rel_dest = dest.relative_to(UPLOAD_DIR).as_posix()
    return f"/uploads/{rel_dest}"


def save_template_image(content: bytes, original_name: str | None) -> dict:
    ext = _safe_ext(original_name)
    if ext not in ALLOWED_TEMPLATE_IMAGE_EXT:
        raise ValueError("Invalid image type; allowed: PNG, JPG, WEBP, GIF")
    stored_name = f"{uuid.uuid4().hex}{ext}"
    filepath = MES_TEMPLATE_IMAGE_DIR / stored_name
    filepath.write_bytes(content)
    return {
        "url": f"/uploads/mes/templates/{stored_name}",
        "filename": stored_name,
        "original_filename": original_name or stored_name,
        "content_type": _resolve_content_type(None, original_name),
    }


from services.mes_bom import active_bom_lines, bom_summary
from services.mes_drawings import active_drawings
from services.mes_routes import active_routes, template_route_summary


def template_counts(template: MesProductTemplate) -> dict[str, int]:
    lines = active_bom_lines(template)
    routes = active_routes(template)
    return {
        "bom_count": len(lines),
        "route_count": len(routes),
        "drawing_count": len(active_drawings(template)),
    }


def template_bom_summary(template: MesProductTemplate) -> dict:
    return bom_summary(active_bom_lines(template))


def serialize_template(template: MesProductTemplate) -> dict:
    counts = template_counts(template)
    summary = template_bom_summary(template)
    route_summary = template_route_summary(template)
    return {
        "id": template.id,
        "code": template.code,
        "name": template.name,
        "category_id": template.category_id,
        "category_name": template.category.name if template.category else None,
        "description": template.description or "",
        "length_mm": template.length_mm,
        "width_mm": template.width_mm,
        "height_mm": template.height_mm,
        "weight_kg": template.weight_kg,
        "image_url": template.image_url,
        "qr_prefix": template.qr_prefix,
        "is_active": bool(template.is_active),
        "deleted_at": template.deleted_at,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
        "created_by": template.created_by,
        **counts,
        "bom_summary": summary,
        "route_summary": route_summary,
        "default_route_id": route_summary["default_route_id"],
        "default_route_name": route_summary["default_route_name"],
        "estimated_total_minutes": route_summary["estimated_total_minutes"],
    }


def _normalize_code(value: str) -> str:
    return (value or "").strip().upper()


def duplicate_template(
    db: Session,
    source_id: int,
    new_code: str,
    username: str,
) -> MesProductTemplate:
    source = (
        db.query(MesProductTemplate)
        .options(
            joinedload(MesProductTemplate.bom_lines),
            joinedload(MesProductTemplate.routes).joinedload(MesProductionRoute.steps).joinedload(
                MesRouteStep.stage
            ),
            joinedload(MesProductTemplate.drawings),
            joinedload(MesProductTemplate.category),
        )
        .filter(
            MesProductTemplate.id == source_id,
            MesProductTemplate.deleted_at.is_(None),
        )
        .first()
    )
    if not source:
        raise ValueError("Template not found")

    code = _normalize_code(new_code)
    if not code:
        raise ValueError("New template code required")

    clash = (
        db.query(MesProductTemplate)
        .filter(
            MesProductTemplate.code == code,
            MesProductTemplate.deleted_at.is_(None),
        )
        .first()
    )
    if clash:
        raise ValueError("Template code already exists")

    copy = MesProductTemplate(
        code=code,
        name=f"{source.name} (copy)",
        category_id=source.category_id,
        description=source.description,
        unit=source.unit,
        length_mm=source.length_mm,
        width_mm=source.width_mm,
        height_mm=source.height_mm,
        weight_kg=source.weight_kg,
        image_url=_copy_upload_file(source.image_url),
        qr_prefix=f"{source.qr_prefix}-COPY" if source.qr_prefix else None,
        is_active=True,
        created_by=username,
    )
    db.add(copy)
    db.flush()

    for line in source.bom_lines or []:
        db.add(
            MesBomLine(
                template_id=copy.id,
                part_id=line.part_id,
                required_quantity=line.required_quantity,
                produced_quantity=0.0,
                accepted_quantity=0.0,
                rejected_quantity=0.0,
                unit=line.unit,
                notes=line.notes,
                drawing_url=_copy_upload_file(line.drawing_url),
                sort_order=line.sort_order,
            )
        )

    for route in source.routes or []:
        if not route.is_active:
            continue
        new_route = MesProductionRoute(
            template_id=copy.id,
            name=route.name,
            version=route.version,
            is_default=route.is_default,
            is_active=True,
            created_by=username,
        )
        db.add(new_route)
        db.flush()
        if route.is_default:
            copy.default_route_id = new_route.id
        for step in route.steps or []:
            db.add(
                MesRouteStep(
                    route_id=new_route.id,
                    stage_id=step.stage_id,
                    step_order=step.step_order,
                    department=step.department,
                    responsible_role=step.responsible_role,
                    estimated_minutes=step.estimated_minutes,
                    required_parts_count=int(step.required_parts_count or 0),
                    completed_parts_count=0,
                    instructions=step.instructions,
                    is_required=step.is_required,
                )
            )

    for drawing in active_drawings(source):
        new_url = _copy_upload_file(drawing.url)
        if not new_url:
            continue
        db.add(
            MesProductDrawing(
                template_id=copy.id,
                title=drawing.title,
                url=new_url,
                filename=Path(new_url).name,
                original_filename=drawing.original_filename,
                content_type=drawing.content_type,
                file_size=drawing.file_size,
                revision=drawing.revision,
                is_primary=drawing.is_primary,
                uploaded_by=username,
            )
        )

    db.flush()
    return copy
