"""Package labels, QR/barcode, passport, tracking, and scan workflows."""

from __future__ import annotations

import base64
import io
import json
import os
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, joinedload

from models import (
    AuditLog,
    MesDispatch,
    MesDispatchPackage,
    MesFinishedGoodsInventory,
    MesJobPackage,
    MesJobRouteStep,
    MesProductionJob,
    PackageLabel,
    PackageLocation,
)
from services.audit import log_action
from services.label_printer import print_package_label

LABEL_PREFIX = "PKG"
LABEL_PATTERN = re.compile(r"^PKG-\d{8}-\d{5}$")

TIMELINE_STAGES = (
    ("lazer", ("Lazer", "Kesish")),
    ("svarshik", ("Svarshik", "Svarka")),
    ("kraska", ("Kraska",)),
    ("qc", ("Tekshiruv", "Nazorat", "QC")),
    ("packaging", ("Upakovka", "Packaging")),
    ("warehouse", ("Sklad", "Ombor")),
    ("dispatch", ("Yuklash", "Dispatch")),
)


def label_fields_for_package(pkg: MesJobPackage) -> dict[str, Any]:
    label = pkg.label
    loc = pkg.storage_location
    return {
        "label_code": label.label_code if label else None,
        "qr_data": label.qr_data if label else None,
        "printed_at": label.printed_at if label else None,
        "warehouse_zone": loc.warehouse_zone if loc else "",
        "rack": loc.rack if loc else "",
        "shelf": loc.shelf if loc else "",
    }


def public_track_url(label_code: str) -> str:
    base = (
        os.getenv("PUBLIC_FRONTEND_URL", "").strip()
        or os.getenv("FRONTEND_PUBLIC_URL", "").strip()
        or "https://azmus-crm.vercel.app"
    ).rstrip("/")
    return f"{base}/track/package/{label_code}"


def generate_label_code(db: Session, *, day: datetime | None = None) -> str:
    now = day or datetime.utcnow()
    date_part = now.strftime("%Y%m%d")
    prefix = f"{LABEL_PREFIX}-{date_part}-"
    existing = (
        db.query(PackageLabel)
        .filter(PackageLabel.label_code.like(f"{prefix}%"))
        .order_by(PackageLabel.id.desc())
        .all()
    )
    max_seq = 0
    for row in existing:
        try:
            max_seq = max(max_seq, int(row.label_code.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}{max_seq + 1:05d}"


def _qr_png_base64(data: str) -> str:
    try:
        import qrcode

        img = qrcode.make(data)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


def _barcode_png_base64(data: str) -> str:
    try:
        from barcode import Code128
        from barcode.writer import ImageWriter

        buf = io.BytesIO()
        Code128(data, writer=ImageWriter()).write(buf, options={"write_text": False})
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


def create_label_for_package(
    db: Session,
    pkg: MesJobPackage,
    *,
    username: str,
    auto_print: bool = True,
) -> PackageLabel:
    existing = (
        db.query(PackageLabel).filter(PackageLabel.package_id == pkg.id).first()
    )
    if existing:
        return existing

    job = pkg.job or db.query(MesProductionJob).filter(MesProductionJob.id == pkg.job_id).first()
    label_code = generate_label_code(db)
    track_url = public_track_url(label_code)
    label = PackageLabel(
        package_id=pkg.id,
        label_code=label_code,
        qr_data=track_url,
        barcode_data=label_code,
    )
    db.add(label)
    db.flush()

    if auto_print:
        try:
            template = job.template if job else None
            printer_name = print_package_label(
                db,
                label,
                package_meta={
                    "product_name": template.name if template else "",
                    "product_code": template.code if template else "",
                    "net_weight_kg": pkg.net_weight_kg,
                    "quantity": 1,
                },
            )
            if printer_name:
                label.printed_at = datetime.utcnow()
                label.printer_name = printer_name
        except Exception as exc:
            log_action(
                db,
                username,
                "print_failed",
                "package_label",
                label.id,
                str(exc),
            )

    log_action(
        db,
        username,
        "create_label",
        "package_label",
        label.id,
        label_code,
    )
    return label


def ensure_labels_for_job_packages(
    db: Session,
    job: MesProductionJob,
    *,
    username: str,
) -> list[PackageLabel]:
    labels = []
    for pkg in job.packages or []:
        if pkg.status not in ("packed", "placed", "received", "loaded"):
            continue
        labels.append(create_label_for_package(db, pkg, username=username))
    return labels


def _match_step(steps: list[MesJobRouteStep], names: tuple[str, ...]) -> MesJobRouteStep | None:
    for step in steps:
        if step.stage_name in names or (step.department or "") in names:
            return step
    return None


def _operator_from_audit(db: Session, step_id: int, field: str) -> tuple[str | None, datetime | None]:
    logs = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type == "mes_job_route_step",
            AuditLog.entity_id == step_id,
        )
        .order_by(AuditLog.created_at.desc())
        .all()
    )
    for log in logs:
        try:
            detail = json.loads(log.details or "{}")
        except json.JSONDecodeError:
            continue
        if detail.get("field") == field and detail.get("new"):
            ts = log.created_at
            return log.username, ts
    return None, None


def build_timeline(db: Session, job: MesProductionJob) -> list[dict[str, Any]]:
    steps = sorted(job.route_steps or [], key=lambda s: (s.step_order, s.id))
    timeline = []
    for key, names in TIMELINE_STAGES:
        step = _match_step(steps, names)
        if not step:
            timeline.append(
                {
                    "stage_key": key,
                    "stage_name": names[0],
                    "operator": None,
                    "accepted_at": None,
                    "started_at": None,
                    "completed_at": None,
                }
            )
            continue
        acc_op, _ = _operator_from_audit(db, step.id, "accepted_at")
        start_op, _ = _operator_from_audit(db, step.id, "started_at")
        comp_op, _ = _operator_from_audit(db, step.id, "completed_at")
        timeline.append(
            {
                "stage_key": key,
                "stage_name": step.stage_name,
                "operator": comp_op or start_op or acc_op,
                "accepted_at": step.accepted_at,
                "started_at": step.started_at,
                "completed_at": step.completed_at,
            }
        )
    return timeline


def load_package_by_label(db: Session, label_code: str) -> tuple[PackageLabel, MesJobPackage] | None:
    label = (
        db.query(PackageLabel)
        .options(
            joinedload(PackageLabel.package)
            .joinedload(MesJobPackage.job)
            .joinedload(MesProductionJob.template),
            joinedload(PackageLabel.package)
            .joinedload(MesJobPackage.job)
            .joinedload(MesProductionJob.route_steps),
            joinedload(PackageLabel.package).joinedload(MesJobPackage.storage_location),
            joinedload(PackageLabel.package).joinedload(MesJobPackage.location),
        )
        .filter(PackageLabel.label_code == label_code.strip())
        .first()
    )
    if not label or not label.package:
        return None
    return label, label.package


def build_passport(db: Session, label_code: str, *, include_internal: bool = True) -> dict | None:
    row = load_package_by_label(db, label_code)
    if not row:
        return None
    label, pkg = row
    job = pkg.job
    template = job.template if job else None
    loc = pkg.storage_location
    dispatch_row = (
        db.query(MesDispatchPackage)
        .filter(MesDispatchPackage.package_id == pkg.id)
        .first()
    )
    return {
        "label_code": label.label_code,
        "package_code": label.label_code,
        "package_number": pkg.package_number,
        "product": template.name if template else "",
        "sku": template.code if template else "",
        "weight_kg": float(pkg.net_weight_kg or 0),
        "gross_weight_kg": float(pkg.gross_weight_kg or 0),
        "length_mm": float(template.length_mm or 0) if template else None,
        "width_mm": float(template.width_mm or 0) if template else None,
        "height_mm": float(template.height_mm or 0) if template else None,
        "customer": job.customer_name if job else "",
        "job_number": job.job_number if job else "",
        "production_date": job.completed_at or job.started_at if job else None,
        "status": pkg.status,
        "quantity": 1,
        "location": {
            "warehouse_zone": loc.warehouse_zone if loc else "",
            "rack": loc.rack if loc else "",
            "shelf": loc.shelf if loc else "",
            "location_code": pkg.location.code if pkg.location else "",
        },
        "printed_at": label.printed_at,
        "printer_name": label.printer_name,
        "qr_data": label.qr_data,
        "barcode_data": label.barcode_data,
        "qr_image_base64": _qr_png_base64(label.qr_data),
        "barcode_image_base64": _barcode_png_base64(label.barcode_data),
        "timeline": build_timeline(db, job) if job and include_internal else [],
        "loaded_at": dispatch_row.loaded_at if dispatch_row else None,
        "loaded_by": dispatch_row.loaded_by if dispatch_row else None,
    }


def build_public_tracking(db: Session, label_code: str) -> dict | None:
    row = load_package_by_label(db, label_code)
    if not row:
        return None
    label, pkg = row
    job = pkg.job
    template = job.template if job else None
    dispatch_pkg = (
        db.query(MesDispatchPackage)
        .filter(MesDispatchPackage.package_id == pkg.id)
        .first()
    )
    dispatch = None
    if dispatch_pkg:
        dispatch = db.query(MesDispatch).filter(MesDispatch.id == dispatch_pkg.dispatch_id).first()

    status = pkg.status
    if dispatch_pkg and dispatch_pkg.status == "loaded":
        status = "loaded"
    elif dispatch_pkg and dispatch_pkg.shipped_at:
        status = "shipped"
    elif pkg.status == "placed":
        status = "in_warehouse"

    return {
        "label_code": label.label_code,
        "product": template.name if template else "",
        "status": status,
        "production_completed_date": job.completed_at if job else None,
        "dispatch_date": dispatch_pkg.shipped_at or dispatch.ship_date if dispatch_pkg else None,
    }


def assign_package_location(
    db: Session,
    *,
    label_code: str,
    warehouse_zone: str,
    rack: str,
    shelf: str,
    username: str,
) -> PackageLocation:
    row = load_package_by_label(db, label_code)
    if not row:
        raise ValueError("Package label not found")
    _, pkg = row
    loc = pkg.storage_location
    if not loc:
        loc = PackageLocation(package_id=pkg.id)
        db.add(loc)
    loc.warehouse_zone = (warehouse_zone or "").strip()
    loc.rack = (rack or "").strip()
    loc.shelf = (shelf or "").strip()
    loc.updated_at = datetime.utcnow()
    log_action(
        db,
        username,
        "assign_location",
        "package_location",
        loc.id,
        json.dumps({"zone": loc.warehouse_zone, "rack": loc.rack, "shelf": loc.shelf}),
    )
    return loc


def scan_dispatch_load(
    db: Session,
    *,
    label_code: str,
    dispatch_id: int,
    username: str,
) -> dict:
    row = load_package_by_label(db, label_code)
    if not row:
        raise ValueError("Invalid package QR — label not found")
    _, pkg = row

    if pkg.status not in ("placed", "received", "packed"):
        raise ValueError(f"Package cannot be loaded (status: {pkg.status})")

    inv = (
        db.query(MesFinishedGoodsInventory)
        .filter(MesFinishedGoodsInventory.package_id == pkg.id)
        .first()
    )
    if not inv or inv.status != "in_stock":
        raise ValueError("Package is not in finished goods inventory")

    dispatch = db.query(MesDispatch).filter(MesDispatch.id == dispatch_id).first()
    if not dispatch:
        raise ValueError("Dispatch not found")

    dp = (
        db.query(MesDispatchPackage)
        .filter(
            MesDispatchPackage.dispatch_id == dispatch_id,
            MesDispatchPackage.package_id == pkg.id,
        )
        .first()
    )
    if not dp:
        dp = MesDispatchPackage(
            dispatch_id=dispatch_id,
            package_id=pkg.id,
            inventory_id=inv.id,
            status="pending",
        )
        db.add(dp)
        db.flush()

    now = datetime.utcnow()
    dp.status = "loaded"
    dp.loaded_by = username
    dp.loaded_at = now
    pkg.status = "loaded"
    log_action(db, username, "scan_load", "mes_dispatch_package", dp.id, label_code)
    return {
        "label_code": label_code,
        "package_id": pkg.id,
        "dispatch_id": dispatch_id,
        "status": "loaded",
        "loaded_by": username,
        "loaded_at": now,
    }


def traceability_dashboard(db: Session) -> dict:
    today = datetime.utcnow().date()
    start = datetime.combine(today, datetime.min.time())

    packages_today = (
        db.query(MesJobPackage)
        .filter(MesJobPackage.created_at >= start)
        .count()
    )
    labels_today = (
        db.query(PackageLabel)
        .filter(PackageLabel.created_at >= start)
        .count()
    )
    printed_today = (
        db.query(PackageLabel)
        .filter(PackageLabel.printed_at.isnot(None), PackageLabel.printed_at >= start)
        .count()
    )
    in_warehouse = (
        db.query(MesJobPackage)
        .filter(MesJobPackage.status.in_(("placed", "received", "packed")))
        .count()
    )
    dispatched_today = (
        db.query(MesDispatchPackage)
        .filter(
            MesDispatchPackage.loaded_at.isnot(None),
            MesDispatchPackage.loaded_at >= start,
        )
        .count()
    )
    return {
        "packages_today": packages_today,
        "printed_labels_today": printed_today,
        "labels_created_today": labels_today,
        "packages_in_warehouse": in_warehouse,
        "packages_dispatched_today": dispatched_today,
    }
