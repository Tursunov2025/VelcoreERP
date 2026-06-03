"""Unified orders + MES jobs feed for executive control center."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session, joinedload

from models import MesProductionJob, Order
from services.mes_jobs import serialize_job
from services.mes_production_monitor import (
    build_route_timeline,
    current_stage_name,
    job_overall_progress_pct,
)

DELAY_GRACE_HOURS = 0


def _utcnow() -> datetime:
    return datetime.utcnow()


def _order_delayed(order: Order, now: datetime) -> bool:
    if order.deleted_at:
        return False
    if order.status == "Tayyor":
        return False
    if order.estimated_finish_at and order.estimated_finish_at < now:
        return True
    created = order.created_at or now
    if (now - created) > timedelta(days=14) and order.status not in ("Tayyor",):
        return True
    return False


def _job_delayed(job: MesProductionJob, now: datetime) -> bool:
    if job.status in ("completed", "cancelled", "draft"):
        return False
    if job.due_date and job.due_date < now:
        return True
    return False


def _serialize_legacy_order(order: Order, now: datetime) -> dict:
    history = sorted(order.history or [], key=lambda h: h.completed_at or h.started_at or datetime.min)
    timeline = [
        {
            "stage": h.stage,
            "status": "completed",
            "at": h.completed_at,
            "operator": h.operator_username,
        }
        for h in history
    ]
    if order.status and (not timeline or timeline[-1]["stage"] != order.status):
        timeline.append({"stage": order.status, "status": "active", "at": order.updated_at, "operator": ""})

    return {
        "type": "order",
        "id": order.id,
        "reference": f"ORD-{order.id}",
        "customer": order.client or "",
        "phone": order.phone or "",
        "title": order.client or "",
        "status": order.status or "",
        "amount": order.amount or "0",
        "destination": order.destination or "",
        "priority": None,
        "progress_pct": 100.0 if order.status == "Tayyor" else max(10.0, len(timeline) * 15),
        "current_stage": order.status or "—",
        "timeline": timeline,
        "is_delayed": _order_delayed(order, now),
        "due_at": order.estimated_finish_at,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "link": f"/orders",
    }


def _serialize_mes_job(job: MesProductionJob, now: datetime) -> dict:
    data = serialize_job(job)
    timeline = build_route_timeline(job)
    return {
        "type": "mes_job",
        "id": job.id,
        "reference": job.job_number,
        "customer": job.customer_name or "",
        "phone": "",
        "title": data.get("template_name") or job.job_number,
        "status": job.status,
        "amount": None,
        "destination": job.order_reference or "",
        "priority": job.priority,
        "progress_pct": job_overall_progress_pct(job),
        "current_stage": current_stage_name(job),
        "timeline": timeline,
        "is_delayed": _job_delayed(job, now),
        "due_at": job.due_date,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "link": f"/mes/jobs/{job.id}",
    }


def list_control_center_items(
    db: Session,
    *,
    q: str = "",
    customer: str = "",
    status: str = "",
    item_type: str = "all",
    delayed_only: bool = False,
    limit: int = 500,
) -> dict[str, Any]:
    now = _utcnow()
    q_lower = (q or "").strip().lower()
    customer_lower = (customer or "").strip().lower()
    status_filter = (status or "").strip().lower()

    items: list[dict] = []

    if item_type in ("all", "order"):
        orders = (
            db.query(Order)
            .options(joinedload(Order.history))
            .filter(Order.deleted_at.is_(None))
            .order_by(Order.updated_at.desc())
            .limit(limit)
            .all()
        )
        for order in orders:
            row = _serialize_legacy_order(order, now)
            if customer_lower and customer_lower not in (row["customer"] or "").lower():
                continue
            if status_filter and status_filter != (row["status"] or "").lower():
                continue
            if q_lower:
                blob = f"{row['reference']} {row['customer']} {row['phone']} {row['status']}".lower()
                if q_lower not in blob:
                    continue
            if delayed_only and not row["is_delayed"]:
                continue
            items.append(row)

    if item_type in ("all", "mes_job", "job"):
        jobs = (
            db.query(MesProductionJob)
            .options(
                joinedload(MesProductionJob.template),
                joinedload(MesProductionJob.route),
                joinedload(MesProductionJob.route_steps),
                joinedload(MesProductionJob.bom_lines),
            )
            .order_by(MesProductionJob.updated_at.desc())
            .limit(limit)
            .all()
        )
        for job in jobs:
            row = _serialize_mes_job(job, now)
            if customer_lower and customer_lower not in (row["customer"] or "").lower():
                continue
            if status_filter and status_filter != (row["status"] or "").lower():
                continue
            if q_lower:
                blob = f"{row['reference']} {row['customer']} {row['title']} {row['status']}".lower()
                if q_lower not in blob:
                    continue
            if delayed_only and not row["is_delayed"]:
                continue
            items.append(row)

    items.sort(key=lambda x: (not x["is_delayed"], x.get("updated_at") or datetime.min), reverse=True)

    delayed_count = sum(1 for i in items if i["is_delayed"])
    active_count = sum(
        1
        for i in items
        if i["status"] not in ("Tayyor", "completed", "cancelled", "draft")
    )

    return {
        "items": items[:limit],
        "summary": {
            "total": len(items),
            "delayed": delayed_count,
            "active": active_count,
            "orders": sum(1 for i in items if i["type"] == "order"),
            "mes_jobs": sum(1 for i in items if i["type"] == "mes_job"),
        },
        "generated_at": now.isoformat(),
    }


def export_items_csv(items: list[dict]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Type",
            "Reference",
            "Customer",
            "Status",
            "Current stage",
            "Progress %",
            "Delayed",
            "Due at",
            "Updated at",
        ]
    )
    for row in items:
        writer.writerow(
            [
                row.get("type"),
                row.get("reference"),
                row.get("customer"),
                row.get("status"),
                row.get("current_stage"),
                row.get("progress_pct"),
                "yes" if row.get("is_delayed") else "no",
                row.get("due_at") or "",
                row.get("updated_at") or "",
            ]
        )
    return output.getvalue()
