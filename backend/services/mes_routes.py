"""MES production route helpers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from models import MesProductTemplate, MesProductionRoute, MesRouteStep


def active_routes(template: MesProductTemplate) -> list[MesProductionRoute]:
    routes = template.routes or []
    return sorted(
        [route for route in routes if route.is_active and route.deleted_at is None],
        key=lambda route: (-route.version, route.id),
    )


def active_route_steps(route: MesProductionRoute) -> list[MesRouteStep]:
    steps = route.steps or []
    return sorted(steps, key=lambda step: (step.step_order, step.id))


def route_estimated_minutes(route: MesProductionRoute) -> int:
    return sum(int(step.estimated_minutes or 0) for step in active_route_steps(route))


def serialize_route_step(step: MesRouteStep) -> dict:
    stage = step.stage
    department = step.department or (stage.department if stage else None)
    return {
        "id": step.id,
        "route_id": step.route_id,
        "stage_id": step.stage_id,
        "stage_name": stage.name if stage else None,
        "stage_color": stage.color if stage else None,
        "step_order": step.step_order,
        "department": department,
        "responsible_role": step.responsible_role,
        "estimated_minutes": step.estimated_minutes,
        "required_parts_count": int(step.required_parts_count or 0),
        "completed_parts_count": int(step.completed_parts_count or 0),
        "started_at": step.started_at,
        "accepted_at": step.accepted_at,
        "completed_at": step.completed_at,
        "instructions": step.instructions or "",
        "is_required": bool(step.is_required),
    }


def serialize_route(route: MesProductionRoute, template: MesProductTemplate | None = None) -> dict:
    steps = active_route_steps(route)
    is_default = bool(route.is_default)
    if template is not None and template.default_route_id:
        is_default = template.default_route_id == route.id
    return {
        "id": route.id,
        "template_id": route.template_id,
        "name": route.name,
        "version": route.version,
        "is_default": is_default,
        "is_active": bool(route.is_active),
        "step_count": len(steps),
        "estimated_total_minutes": route_estimated_minutes(route),
        "steps": [serialize_route_step(step) for step in steps],
        "created_at": route.created_at,
        "created_by": route.created_by,
    }


def template_route_summary(template: MesProductTemplate) -> dict:
    routes = active_routes(template)
    default_route = None
    if template.default_route_id:
        default_route = next((r for r in routes if r.id == template.default_route_id), None)
    if default_route is None:
        default_route = next((r for r in routes if r.is_default), None)
    if default_route is None and routes:
        default_route = routes[0]

    return {
        "route_count": len(routes),
        "default_route_id": default_route.id if default_route else None,
        "default_route_name": default_route.name if default_route else None,
        "default_route_version": default_route.version if default_route else None,
        "estimated_total_minutes": route_estimated_minutes(default_route) if default_route else 0,
    }


def get_active_route(db: Session, template_id: int, route_id: int) -> MesProductionRoute | None:
    from sqlalchemy.orm import joinedload

    return (
        db.query(MesProductionRoute)
        .options(
            joinedload(MesProductionRoute.steps).joinedload(MesRouteStep.stage),
        )
        .filter(
            MesProductionRoute.id == route_id,
            MesProductionRoute.template_id == template_id,
            MesProductionRoute.is_active.is_(True),
            MesProductionRoute.deleted_at.is_(None),
        )
        .first()
    )


def next_step_order(route: MesProductionRoute) -> int:
    steps = active_route_steps(route)
    if not steps:
        return 0
    return max(step.step_order for step in steps) + 1


def copy_route_steps(source: MesProductionRoute, target: MesProductionRoute) -> None:
    for step in active_route_steps(source):
        target.steps.append(
            MesRouteStep(
                stage_id=step.stage_id,
                step_order=step.step_order,
                department=step.department,
                responsible_role=step.responsible_role,
                estimated_minutes=step.estimated_minutes,
                required_parts_count=int(step.required_parts_count or 0),
                completed_parts_count=0,
                instructions=step.instructions or "",
                is_required=bool(step.is_required),
            )
        )


def set_default_route(db: Session, template: MesProductTemplate, route: MesProductionRoute) -> None:
    for item in template.routes or []:
        if item.is_active and item.deleted_at is None:
            item.is_default = item.id == route.id
    route.is_default = True
    template.default_route_id = route.id
