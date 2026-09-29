"""MES Yig‘ish template detail helpers."""

from __future__ import annotations

from sqlalchemy.orm import joinedload, Session

from models import Material, MesProductPart, MesProductTemplate, MesYigishLine


def active_yigish_lines(template: MesProductTemplate) -> list[MesYigishLine]:
    lines = template.yigish_lines or []
    return sorted(
        [
            line
            for line in lines
            if line.is_active and line.deleted_at is None
        ],
        key=lambda line: (line.sort_order, line.id),
    )


def yigish_summary(lines: list[MesYigishLine]) -> dict[str, float | int]:
    return {
        "parts_count": len(lines),
        "total_required_quantity": sum(
            float(line.required_quantity or 0)
            for line in lines
        ),
    }


def serialize_yigish_line(line: MesYigishLine) -> dict:
    part = line.part
    material = line.material

    return {
        "id": line.id,
        "template_id": line.template_id,
        "part_id": line.part_id,
        "material_id": line.material_id,
        "part_number": part.part_number if part else (material.code if material else None),
        "part_name": part.name if part else (material.name if material else None),
        "part_unit": part.unit if part else (material.unit if material else line.unit),
        "part_is_active": bool(part.is_active) if part else bool(material.is_active) if material else False,
        "part_deleted": part.deleted_at is not None if part else False,
        "material_code": material.code if material else None,
        "material_name": material.name if material else None,
        "material_type": material.material_type if material else None,
        "material_is_active": bool(material.is_active) if material else False,
        "required_quantity": float(line.required_quantity or 0),
        "unit": line.unit or (part.unit if part else material.unit if material else None),
        "notes": line.notes or "",
        "sort_order": line.sort_order,
        "is_active": bool(line.is_active),
        "created_at": line.created_at,
    }


def serialize_yigish(template: MesProductTemplate) -> dict:
    lines = active_yigish_lines(template)

    return {
        "lines": [serialize_yigish_line(line) for line in lines],
        "summary": yigish_summary(lines),
    }


def next_yigish_sort_order(db: Session, template_id: int) -> int:
    last = (
        db.query(MesYigishLine)
        .filter(
            MesYigishLine.template_id == template_id,
            MesYigishLine.is_active.is_(True),
            MesYigishLine.deleted_at.is_(None),
        )
        .order_by(
            MesYigishLine.sort_order.desc(),
            MesYigishLine.id.desc(),
        )
        .first()
    )

    if not last:
        return 0

    return int(last.sort_order or 0) + 1


def find_yigish_line(
    db: Session,
    template_id: int,
    line_id: int,
    *,
    active_only: bool = True,
) -> MesYigishLine | None:
    query = (
        db.query(MesYigishLine)
        .options(
            joinedload(MesYigishLine.part),
            joinedload(MesYigishLine.material),
        )
        .filter(
            MesYigishLine.id == line_id,
            MesYigishLine.template_id == template_id,
        )
    )

    if active_only:
        query = query.filter(
            MesYigishLine.is_active.is_(True),
            MesYigishLine.deleted_at.is_(None),
        )

    return query.first()


def get_active_yigish_material(
    db: Session,
    material_id: int,
) -> Material:
    material = (
        db.query(Material)
        .filter(
            Material.id == material_id,
            Material.is_active.is_(True),
        )
        .first()
    )
    if not material:
        raise ValueError("Material not found or inactive")
    return material


def get_active_yigish_part(
    db: Session,
    part_id: int,
) -> MesProductPart:
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
