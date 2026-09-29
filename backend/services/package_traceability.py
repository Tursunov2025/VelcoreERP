"""Package labels, QR/barcode, passport, tracking, and scan workflows."""

from __future__ import annotations

import base64
import io
import json
import os
import re
import secrets
import math
from datetime import datetime
from typing import Any

from sqlalchemy import case, or_, text
from sqlalchemy.orm import Session, joinedload

from models import (
    AuditLog,
    MesDispatch,
    MesDispatchPackage,
    MesFinishedGoodsInventory,
    MesJobPackage,
    MesJobRework,
    MesJobRouteStep,
    MesLoadCorrection,
    MesProductionJob,
    PackageLabel,
    PackageLocation,
    ProductPassport,
    ProductPassportSequence,
    MesShipmentItem,
    MesTrip,
    MesTripCommand,
    MesTripLocation,
    MesTripTrackingSession,
)
from services.audit import log_action
from services.feature_flags import print_agent_enabled, traceability_enabled
from services.print_jobs import queue_print_for_label

LABEL_PREFIX = "PKG"
LABEL_PATTERN = re.compile(r"^PKG-\d{8}-\d{5}$")

TIMELINE_STAGES = (
    ("lazer", ("Lazer", "Kesish")),
    ("svarshik", ("Svarshik", "Svarka")),
    ("kraska", ("Kraska",)),
    ("qc", ("Tekshiruv", "Nazorat", "QC")),
    ("packaging", ("Upakovka", "Packaging")),
    ("warehouse", ("Sklad", "Ombor")),
    ("loading", ("Yuklash", "Dispatch")),
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

    if not traceability_enabled():
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

    if auto_print and print_agent_enabled():
        try:
            print_job = queue_print_for_label(db, label, pkg, username=username)
            if print_job and print_job.status == "completed":
                label.printed_at = print_job.printed_at
                label.printer_name = print_job.printer_name
            log_action(
                db,
                username,
                "queue_print",
                "print_job",
                print_job.id if print_job else label.id,
                label.label_code,
            )
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
    if not traceability_enabled():
        return []
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
                    "duration_seconds": None,
                }
            )
            continue
        acc_op, _ = _operator_from_audit(db, step.id, "accepted_at")
        start_op, _ = _operator_from_audit(db, step.id, "started_at")
        comp_op, _ = _operator_from_audit(db, step.id, "completed_at")
        result = None
        if key == "qc" and step.completed_at:
            open_rework = db.query(MesJobRework).filter(
                MesJobRework.job_id == job.id,
                MesJobRework.status.in_(("pending", "in_progress")),
            ).count()
            rejected = sum(
                float((line.qc_rejected_quantity if job.project_id else line.rejected_quantity) or 0)
                for line in (job.bom_lines or [])
            )
            result = "qc_pass" if rejected <= 0 and open_rework == 0 else "qc_fail"
        timeline.append(
            {
                "stage_key": key,
                "stage_name": step.stage_name,
                "operator": comp_op or start_op or acc_op,
                "accepted_at": step.accepted_at,
                "started_at": step.started_at,
                "completed_at": step.completed_at,
                "duration_seconds": (step.completed_at - step.started_at).total_seconds() if step.completed_at and step.started_at else None,
                "result": result,
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
    passport_total = db.query(ProductPassport).count()
    passport_produced_today = db.query(ProductPassport).filter(ProductPassport.created_at >= start).count()
    passport_packed = db.query(ProductPassport).filter(ProductPassport.status == "packed").count()
    passport_shipped = db.query(ProductPassport).filter(ProductPassport.status.in_(("loaded", "shipped", "in_transit"))).count()
    passport_delivered = db.query(ProductPassport).filter(ProductPassport.status.in_(("delivered", "accepted"))).count()
    passport_issues = db.query(MesJobRework).count()
    return {
        "packages_today": packages_today,
        "printed_labels_today": printed_today,
        "labels_created_today": labels_today,
        "packages_in_warehouse": in_warehouse,
        "packages_dispatched_today": dispatched_today,
        "passport_total": passport_total,
        "passport_produced_today": passport_produced_today,
        "passport_packed": passport_packed,
        "passport_shipped": passport_shipped,
        "passport_delivered": passport_delivered,
        "passport_issues": passport_issues,
    }


def product_passport_public_url(token: str) -> str:
    """Return a compact, share-safe URL used as QR payload."""
    base = (
        os.getenv("PUBLIC_FRONTEND_URL", "").strip()
        or os.getenv("FRONTEND_PUBLIC_URL", "").strip()
        or "https://azmus-crm.vercel.app"
    ).rstrip("/")
    return f"{base}/track/product/{token}"


def _next_product_serial(db: Session, year: int) -> str:
    allocator = (
        db.query(ProductPassportSequence)
        .filter(ProductPassportSequence.year == year)
        .with_for_update()
        .first()
    )
    if allocator is None:
        allocator = ProductPassportSequence(year=year, next_value=1)
        db.add(allocator)
        db.flush()
    value = allocator.next_value
    allocator.next_value = value + 1
    return f"PRD-{year}-{value:06d}"


def _passport_status(package_status: str) -> str:
    return {
        "pending": "created",
        "packed": "packed",
        "received": "in_warehouse",
        "placed": "in_warehouse",
        "loaded": "loaded",
    }.get(package_status or "", package_status or "finished")


def _effective_passport_status(package_status: str, trip_status: str | None) -> str:
    """Prefer the authoritative shipment lifecycle once a unit is on a trip."""
    normalized_trip = (trip_status or "").strip().lower()
    if normalized_trip in {"loaded", "dispatched", "in_transit", "arrived", "delivered", "accepted"}:
        return normalized_trip
    return _passport_status(package_status)


def _timeline_event(
    stage_key: str,
    stage_name: str,
    *,
    operator: str | None,
    started_at: datetime | None,
    completed_at: datetime | None,
    result: str,
) -> dict[str, Any]:
    duration = None
    if started_at and completed_at:
        duration = max(0.0, (completed_at - started_at).total_seconds())
    return {
        "stage_key": stage_key,
        "stage_name": stage_name,
        "operator": operator,
        "accepted_at": None,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": duration,
        "result": result,
    }


def _upsert_timeline_event(timeline: list[dict[str, Any]], event: dict[str, Any]) -> None:
    """Replace a route placeholder, otherwise append one authoritative event."""
    for index, current in enumerate(timeline):
        if current.get("stage_key") == event["stage_key"]:
            timeline[index] = event
            return
    timeline.append(event)


def serialize_product_passport(db: Session, passport: ProductPassport, *, include_internal: bool = True) -> dict[str, Any]:
    package = passport.package or db.query(MesJobPackage).filter(MesJobPackage.id == passport.package_id).first()
    job = passport.job or db.query(MesProductionJob).filter(MesProductionJob.id == passport.job_id).first()
    template = passport.template or (job.template if job else None)
    project = passport.project or (job.project if job else None)
    line = passport.project_line or (job.project_line if job else None)
    label = package.label if package else None
    dispatch_pkg = (
        db.query(MesDispatchPackage).filter(MesDispatchPackage.package_id == passport.package_id).first()
        if package else None
    )
    dispatch = None
    trip = None
    if dispatch_pkg:
        dispatch = db.query(MesDispatch).filter(MesDispatch.id == dispatch_pkg.dispatch_id).first()
        if dispatch and dispatch.trip_id:
            trip = db.query(MesTrip).filter(MesTrip.id == dispatch.trip_id).first()
    shipment_item = (
        db.query(MesShipmentItem)
        .filter(MesShipmentItem.package_id == passport.package_id)
        .order_by(
            case((MesShipmentItem.assignment_status == "active", 0), else_=1),
            MesShipmentItem.updated_at.desc(), MesShipmentItem.id.desc(),
        )
        .first()
        if package else None
    )
    # Canonical lifecycle shipments may be linked directly through
    # MesShipmentItem without a legacy MesDispatchPackage mirror.
    if shipment_item and not trip:
        trip = db.query(MesTrip).filter(MesTrip.id == shipment_item.trip_id).first()
    if shipment_item and shipment_item.dispatch_id and not dispatch:
        dispatch = db.query(MesDispatch).filter(MesDispatch.id == shipment_item.dispatch_id).first()
    reworks = []
    if job:
        for row in db.query(MesJobRework).filter(MesJobRework.job_id == job.id).order_by(MesJobRework.created_at).all():
            reworks.append({
                "id": row.id,
                "stage": "QC / Rework",
                "issue_type": "rework",
                "quantity": row.quantity,
                "status": row.status,
                "detected_by": row.created_by,
                "detected_at": row.created_at,
                "resolved_by": row.completed_by,
                "resolved_at": row.completed_at,
                "notes": row.notes or "",
            })
    package_status = package.status if package else passport.status
    vehicle = trip.vehicle if trip else None
    driver_name = trip.driver_name_snapshot if trip else ""
    if trip and trip.driver_user_id and not driver_name:
        profile = db.execute(
            text("SELECT full_name, phone FROM user_identity_profiles WHERE user_id = :uid"),
            {"uid": trip.driver_user_id},
        ).mappings().first()
        driver_name = profile["full_name"] if profile else ""
    route_timeline = build_timeline(db, job) if job else []
    timeline: list[dict[str, Any]] = []
    if project:
        timeline.append(_timeline_event(
            "project", "Project", operator=project.created_by,
            started_at=project.created_at, completed_at=project.created_at,
            result="created",
        ))
    release = job.project_release_snapshot if job else None
    if release:
        timeline.append(_timeline_event(
            "mes_release", "MES Release", operator=release.released_by,
            started_at=release.released_at, completed_at=release.released_at,
            result="released",
        ))
    for row in route_timeline:
        timeline.append(row)
        if row.get("stage_key") == "qc":
            for item in reworks:
                timeline.append(_timeline_event(
                    f"rework-{item['id']}", "QC / Rework",
                    operator=item["resolved_by"] or item["detected_by"],
                    started_at=item["detected_at"], completed_at=item["resolved_at"],
                    result="rework_completed" if item["status"] == "completed" else item["status"],
                ))

    corrections = (
        db.query(MesLoadCorrection)
        .filter(or_(
            MesLoadCorrection.package_id == passport.package_id,
            MesLoadCorrection.replacement_package_id == passport.package_id,
        ))
        .order_by(MesLoadCorrection.created_at, MesLoadCorrection.id)
        .all()
        if package else []
    )
    for correction in corrections:
        event = _timeline_event(
            f"load-correction-{correction.id}", "Load correction",
            operator=correction.actor, started_at=correction.created_at,
            completed_at=correction.created_at, result=correction.action.lower(),
        )
        event.update({
            "reason": correction.reason,
            "from_trip": correction.trip.trip_number if correction.trip else None,
            "to_trip": correction.target_trip.trip_number if correction.target_trip else None,
            "package_number": correction.package.package_number if correction.package else None,
            "replacement_package_number": (
                correction.replacement_package.package_number if correction.replacement_package else None
            ),
        })
        timeline.append(event)

    if trip:
        commands: dict[str, MesTripCommand] = {}
        for command in (
            db.query(MesTripCommand)
            .filter(MesTripCommand.trip_id == trip.id)
            .order_by(MesTripCommand.created_at, MesTripCommand.id)
            .all()
        ):
            commands.setdefault(command.command_type, command)

        loading_command = commands.get("confirm_loading")
        if loading_command:
            _upsert_timeline_event(timeline, _timeline_event(
                "loading", "Loading", operator=loading_command.actor,
                started_at=None, completed_at=loading_command.created_at, result="loaded",
            ))
        dispatch_command = commands.get("dispatch")
        if dispatch_command or trip.actual_departure_at:
            dispatch_at = trip.actual_departure_at or dispatch_command.created_at
            _upsert_timeline_event(timeline, _timeline_event(
                "dispatch", "Dispatch", operator=dispatch_command.actor if dispatch_command else None,
                started_at=None, completed_at=dispatch_at, result="dispatched",
            ))

        tracking_session = (
            db.query(MesTripTrackingSession)
            .filter(MesTripTrackingSession.trip_id == trip.id)
            .order_by(MesTripTrackingSession.started_at, MesTripTrackingSession.id)
            .first()
        )
        first_location = (
            db.query(MesTripLocation)
            .filter(MesTripLocation.trip_id == trip.id)
            .order_by(MesTripLocation.captured_at, MesTripLocation.id)
            .first()
        )
        if tracking_session or first_location:
            gps_end = first_location.captured_at if first_location else None
            gps_actor = trip.driver_user.username if trip.driver_user else None
            _upsert_timeline_event(timeline, _timeline_event(
                "gps_in_transit", "GPS / In transit", operator=gps_actor,
                started_at=tracking_session.started_at if tracking_session else None,
                completed_at=gps_end, result="in_transit",
            ))

        arrival_command = commands.get("confirm_arrival")
        if arrival_command or trip.arrived_at:
            _upsert_timeline_event(timeline, _timeline_event(
                "arrival", "Arrival", operator=arrival_command.actor if arrival_command else None,
                started_at=None, completed_at=trip.arrived_at or arrival_command.created_at,
                result="arrived",
            ))
        delivery_command = commands.get("delivery")
        delivered_at = shipment_item.delivered_at if shipment_item else None
        if delivery_command or delivered_at:
            _upsert_timeline_event(timeline, _timeline_event(
                "delivery", "Delivery", operator=delivery_command.actor if delivery_command else None,
                started_at=None, completed_at=delivered_at or delivery_command.created_at,
                result="delivered",
            ))
        acceptance_command = commands.get("acceptance")
        accepted_at = shipment_item.accepted_at if shipment_item else None
        if acceptance_command or accepted_at:
            _upsert_timeline_event(timeline, _timeline_event(
                "acceptance", "Acceptance", operator=acceptance_command.actor if acceptance_command else None,
                started_at=None, completed_at=accepted_at or acceptance_command.created_at,
                result="accepted",
            ))

    if not include_internal:
        timeline = [{**row, "operator": None} for row in timeline]
    timeline.sort(key=lambda row: (
        row.get("started_at") or row.get("completed_at") or datetime.min,
        row.get("stage_key") or "",
    ))
    public_reworks = reworks if include_internal else [
        {key: value for key, value in item.items() if key not in {"detected_by", "resolved_by"}}
        for item in reworks
    ]
    return {
        "id": passport.id,
        "serial_number": passport.serial_number,
        "qr_token": passport.qr_token if include_internal else None,
        "qr_data": passport.qr_data,
        "product_code": template.code if template else "",
        "product_name": template.name if template else "",
        "unit_index": passport.unit_index,
        "unit_quantity": passport.unit_quantity,
        "status": _effective_passport_status(package_status, trip.status if trip else None),
        "created_at": passport.created_at,
        "finalized_at": passport.finalized_at,
        "project": {
            "id": project.id if project else None,
            "code": project.project_code if project else "",
            "name": project.project_name if project else "",
            "line_id": line.id if line else passport.project_line_id,
        },
        "job": {"id": job.id if job else None, "number": job.job_number if job else ""},
        "package": {
            "id": package.id if package else None,
            "number": package.package_number if package else "",
            "status": package_status,
            "created_at": package.created_at if package else None,
            "net_weight_kg": float(package.net_weight_kg or 0) if package else 0,
            "gross_weight_kg": float(package.gross_weight_kg or 0) if package else 0,
        },
        "shipment": {
            "dispatch_number": dispatch.dispatch_number if dispatch else "",
            "trip_number": trip.trip_number if trip else "",
            "status": trip.status if trip else (dispatch.status if dispatch else ""),
            "destination": (
                (trip.destination_address or "") if trip else ""
            ) or (
                " · ".join(filter(None, [trip.destination_city, trip.destination_site])) if trip else ""
            ) or (dispatch.destination_city if dispatch else ""),
            "vehicle": vehicle.registration_number if vehicle else (dispatch.vehicle_number if dispatch else ""),
            "driver": driver_name or (dispatch.driver_name if dispatch else ""),
            "loaded_at": dispatch_pkg.loaded_at if dispatch_pkg else None,
            "delivered_at": shipment_item.delivered_at if shipment_item else (dispatch.delivered_at if dispatch else None),
            "accepted_at": shipment_item.accepted_at if shipment_item else (dispatch.accepted_at if dispatch else None),
        },
        "timeline": timeline,
        "quality": {"issues": public_reworks, "issue_count": len(public_reworks), "rework_count": sum(1 for x in public_reworks if x["issue_type"] == "rework")},
        "metrics": {"production_lead_time_seconds": None, "touch_time_seconds": None, "waiting_time_seconds": None},
    }


def generate_product_passports_for_package(db: Session, package_id: int, *, username: str) -> list[ProductPassport]:
    package = (
        db.query(MesJobPackage)
        .filter(MesJobPackage.id == package_id)
        .first()
    )
    if not package or package.status not in {"packed", "received", "placed", "loaded"}:
        raise ValueError("Product passports are available after packaging")
    ordered_quantity = max(0.000001, float(package.quantity or 1))
    quantity = max(1, int(math.ceil(ordered_quantity)))
    existing = db.query(ProductPassport).filter(ProductPassport.package_id == package.id).order_by(ProductPassport.unit_index).all()
    by_index = {row.unit_index: row for row in existing}
    now = datetime.utcnow()
    for index in range(1, quantity + 1):
        if index in by_index:
            continue
        serial = _next_product_serial(db, now.year)
        token = secrets.token_urlsafe(18)
        unit_quantity = min(1.0, max(0.000001, ordered_quantity - (index - 1)))
        row = ProductPassport(
            serial_number=serial, qr_token=token, qr_data=product_passport_public_url(token),
            package_id=package.id, job_id=package.job_id, project_id=package.project_id,
            project_line_id=package.project_line_id, template_id=package.job.template_id,
            unit_index=index, unit_quantity=unit_quantity, status=_passport_status(package.status),
            finalized_at=now, created_by=username,
        )
        db.add(row); db.flush(); by_index[index] = row
        log_action(db, username, "product_passport.generate", "product_passport", row.id, serial)
    return [by_index[i] for i in sorted(by_index)]


def list_product_passports(db: Session, *, serial: str = "", product: str = "", project: str = "", package: str = "", trip: str = "", status: str = "", date_from: str = "", date_to: str = "", with_issues: bool = False) -> list[dict[str, Any]]:
    query = db.query(ProductPassport).order_by(ProductPassport.created_at.desc(), ProductPassport.id.desc())
    if serial:
        query = query.filter(ProductPassport.serial_number.ilike(f"%{serial.strip()}%"))
    rows = query.limit(500).all()
    result = []
    for row in rows:
        data = serialize_product_passport(db, row, include_internal=False)
        if product and product.lower() not in f"{data['product_code']} {data['product_name']}".lower():
            continue
        if project and project.lower() not in f"{data['project'].get('code','')} {data['project'].get('name','')}".lower():
            continue
        if package and package.lower() not in f"{data['package'].get('id','')} {data['package'].get('number','')}".lower():
            continue
        if trip and trip.lower() not in f"{data['shipment'].get('trip_number','')} {data['shipment'].get('dispatch_number','')}".lower():
            continue
        created = row.created_at.date().isoformat() if row.created_at else ""
        if date_from and created < date_from:
            continue
        if date_to and created > date_to:
            continue
        if status and data["status"] != status:
            continue
        if with_issues and not data["quality"]["issue_count"]:
            continue
        result.append(data)
    return result



def build_product_label_png(passport: ProductPassport, data: dict[str, Any], *, size: str = "100x50") -> bytes:
    """Render a professional printable product label without writing files."""
    from PIL import Image, ImageDraw, ImageFont
    import qrcode
    from datetime import datetime

    if size == "60x60":
        width, height = 600, 600
        pad = 22
        qr_box = 250
        header_h = 72
        title_size = 26
        body_size = 18
        small_size = 14
        tiny_size = 12
        serial_max = 26
        value_wrap = 20
    elif size == "a4":
        width, height = 1240, 1754
        pad = 42
        qr_box = 470
        header_h = 120
        title_size = 44
        body_size = 28
        small_size = 22
        tiny_size = 18
        serial_max = 42
        value_wrap = 40
    else:  # 100x50
        width, height = 900, 560
        pad = 26
        qr_box = 250
        header_h = 84
        title_size = 34
        body_size = 22
        small_size = 18
        tiny_size = 15
        serial_max = 30
        value_wrap = 28

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    def load_font(name: str, size: int):
        candidates = [
            f"/usr/share/fonts/truetype/dejavu/{name}",
            f"/usr/local/share/fonts/{name}",
            name,
        ]
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()

    title_font = load_font("DejaVuSans-Bold.ttf", title_size)
    body_font = load_font("DejaVuSans.ttf", body_size)
    small_font = load_font("DejaVuSans.ttf", small_size)
    bold_font = load_font("DejaVuSans-Bold.ttf", body_size)
    tiny_font = load_font("DejaVuSans.ttf", tiny_size)

    def text(v):
        if v is None:
            return "—"
        v = str(v).strip()
        return v if v else "—"

    def wrap_text(value: str, width_chars: int):
        value = text(value)
        if value == "—":
            return ["—"]
        words = value.split()
        if not words:
            return [value[:width_chars]]
        lines = []
        line = ""
        for word in words:
            trial = word if not line else line + " " + word
            if len(trial) <= width_chars:
                line = trial
            else:
                if line:
                    lines.append(line)
                while len(word) > width_chars:
                    lines.append(word[:width_chars])
                    word = word[width_chars:]
                line = word
        if line:
            lines.append(line)
        return lines[:3]

    def format_status(v):
        value = text(v)
        return value.replace("_", " ").title()

    def format_created(v):
        if not v:
            return "—"
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d %H:%M")
        try:
            raw = str(v).replace("T", " ")
            return raw[:16]
        except Exception:
            return text(v)

    # Outer border
    draw.rounded_rectangle(
        [(4, 4), (width - 5, height - 5)],
        radius=18,
        outline="black",
        width=3
    )

    # Header
    draw.rounded_rectangle(
        [(pad, pad), (width - pad, pad + header_h)],
        radius=16,
        fill="black",
        outline="black",
        width=2
    )
    draw.text((pad + 18, pad + 10), "VELCORE", fill="white", font=title_font)
    subtitle_y = pad + 14 + title_size
    draw.text((pad + 20, subtitle_y), "PRODUCT LABEL / PASSPORT", fill="white", font=small_font)

    project_text = text(f"{data.get('project', {}).get('code', '')} {data.get('project', {}).get('name', '')}".strip())
    package_text = text(data.get("package", {}).get("number"))
    status_text = format_status(data.get("status"))
    created_text = format_created(data.get("created_at"))

    # QR
    qr = qrcode.make(passport.qr_data).convert("RGB").resize((qr_box, qr_box))
    qr_x = width - pad - qr_box
    qr_y = pad + header_h + 18
    img.paste(qr, (qr_x, qr_y))
    draw.rectangle([(qr_x - 2, qr_y - 2), (qr_x + qr_box + 2, qr_y + qr_box + 2)], outline="black", width=2)
    draw.text((qr_x, qr_y + qr_box + 10), "Scan for passport / tracking", fill="black", font=tiny_font)

    # Left content region
    left_x = pad + 10
    left_y = pad + header_h + 18
    left_w = qr_x - left_x - 24

    # Serial box
    serial_h = 74 if size != "a4" else 96
    draw.rounded_rectangle(
        [(left_x, left_y), (left_x + left_w, left_y + serial_h)],
        radius=14,
        outline="black",
        width=2
    )
    draw.text((left_x + 14, left_y + 8), "SERIAL NUMBER", fill="black", font=small_font)
    serial_lines = wrap_text(text(data.get("serial_number")), serial_max)
    sy = left_y + 34
    for line in serial_lines[:2]:
        draw.text((left_x + 14, sy), line, fill="black", font=bold_font)
        sy += body_size + 4

    # Detail rows
    current_y = left_y + serial_h + 14
    row_gap = 12 if size != "a4" else 16
    row_h = 54 if size == "60x60" else 58 if size == "100x50" else 74

    product_code = text(data.get("product_code"))
    product_name = text(data.get("product_name"))

    rows = [
        ("Product code", product_code),
        ("Product name", product_name),
        ("Project", project_text),
        ("Package", package_text),
        ("Status", status_text),
        ("Created", created_text),
    ]

    label_x = left_x + 12
    value_x = left_x + 165 if size != "a4" else left_x + 220

    for label, value in rows:
        draw.rounded_rectangle(
            [(left_x, current_y), (left_x + left_w, current_y + row_h)],
            radius=12,
            outline="black",
            width=1
        )
        draw.text((label_x, current_y + 10), f"{label}:", fill="black", font=small_font)

        lines = wrap_text(value, value_wrap)
        vy = current_y + 8
        for line in lines[:2]:
            draw.text((value_x, vy), line, fill="black", font=body_font)
            vy += body_size + 2

        current_y += row_h + row_gap

    # Footer
    footer_text = text(getattr(passport, "label_code", None) or getattr(passport, "qr_data", None))
    footer_y = height - pad - 28
    draw.line([(pad, footer_y - 8), (width - pad, footer_y - 8)], fill="black", width=1)
    draw.text((pad, footer_y), f"Label ID: {footer_text[:80]}", fill="black", font=tiny_font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def build_product_label_pdf(passport: ProductPassport, data: dict[str, Any], *, size: str = "a4") -> bytes:
    """Wrap the rendered QR label in a real PDF page using Pillow's PDF writer."""
    from PIL import Image

    image = Image.open(io.BytesIO(build_product_label_png(passport, data, size=size))).convert("RGB")
    buf = io.BytesIO()
    image.save(buf, format="PDF", resolution=150.0)
    return buf.getvalue()


def build_product_labels_sheet_pdf(
    db: Session,
    serial_numbers: list[str],
    *,
    size: str = "60x60",
    max_batch: int = 500,
) -> tuple[bytes, list[str]]:
    """Render selected unit passports as one bounded, in-memory A4 sheet.

    The passport table remains the sole identity source.  No temporary files are
    created, and the caller receives the serial order used for the sheet.
    """
    from PIL import Image, ImageDraw

    if size not in {"60x60", "100x50"}:
        raise ValueError("Unsupported label sheet size")
    ordered = list(dict.fromkeys(str(value).strip() for value in serial_numbers if str(value).strip()))
    if not ordered or len(ordered) > max_batch:
        raise ValueError(f"Batch size must be between 1 and {max_batch}")
    rows = db.query(ProductPassport).filter(ProductPassport.serial_number.in_(ordered)).all()
    by_serial = {row.serial_number: row for row in rows}
    missing = [serial for serial in ordered if serial not in by_serial]
    if missing:
        raise ValueError("One or more product passports were not found")

    # A4 at 150dpi. Three columns by four rows leaves print-safe margins while
    # preserving a readable 60x60 label footprint.
    page_width, page_height = 1240, 1754
    columns, rows_per_page = (3, 4)
    margin_x, margin_y, gap = 55, 55, 24
    cell_width = (page_width - 2 * margin_x - (columns - 1) * gap) // columns
    cell_height = (page_height - 2 * margin_y - (rows_per_page - 1) * gap) // rows_per_page
    label_size = min(cell_width, cell_height)
    pages: list[Image.Image] = []
    current: Image.Image | None = None
    for index, serial in enumerate(ordered):
        slot = index % (columns * rows_per_page)
        if slot == 0:
            current = Image.new("RGB", (page_width, page_height), "white")
            pages.append(current)
        assert current is not None
        passport = by_serial[serial]
        data = serialize_product_passport(db, passport)
        label = Image.open(io.BytesIO(build_product_label_png(passport, data, size=size))).convert("RGB")
        label.thumbnail((label_size, label_size), Image.Resampling.LANCZOS)
        col, row = slot % columns, slot // columns
        x = margin_x + col * (cell_width + gap) + (cell_width - label.width) // 2
        y = margin_y + row * (cell_height + gap) + (cell_height - label.height) // 2
        current.paste(label, (x, y))
        ImageDraw.Draw(current).rectangle((x, y, x + label.width - 1, y + label.height - 1), outline="#d1d5db", width=2)
    output = io.BytesIO()
    pages[0].save(output, format="PDF", resolution=150.0, save_all=True, append_images=pages[1:])
    return output.getvalue(), ordered
