"""Cloud print queue — jobs for local Windows print agents."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session, joinedload

from models import (
    MesJobPackage,
    MesProductionJob,
    PackageLabel,
    PrintAgentHeartbeat,
    PrintJob,
)
from services.label_printer import get_printers_config, pick_auto_printer, print_package_label
from services.print_label_image import build_label_png_bytes, label_meta_from_package
from services.settings_store import get_settings_group

PRINT_STATUSES = ("pending", "printing", "completed", "failed")
AGENT_ONLINE_SECONDS = int(os.getenv("PRINT_AGENT_ONLINE_SECONDS", "45"))


def _printer_uses_cloud_agent(printer: dict | None) -> bool:
    if not printer:
        return True
    conn = (printer.get("connection_type") or "").strip().lower()
    if conn in ("cloud_agent", "windows_usb", "usb", "local"):
        return True
    if printer.get("use_cloud_agent"):
        return True
    if (printer.get("brand") or "").lower() == "xprinter" and not (printer.get("ip_address") or "").strip():
        return True
    return False


def resolve_printer_for_job(db: Session) -> dict | None:
    printers = get_printers_config(db)
    for p in printers:
        if p.get("auto_print_enabled") and _printer_uses_cloud_agent(p):
            return p
    for p in printers:
        if _printer_uses_cloud_agent(p):
            return p
    return pick_auto_printer(printers)


def printer_display_name(printer: dict | None) -> str:
    if not printer:
        return "default"
    return (
        (printer.get("name") or printer.get("printer_name") or "").strip()
        or (printer.get("windows_printer_name") or "").strip()
        or "default"
    )


def create_print_job(
    db: Session,
    *,
    package_id: int,
    label_code: str,
    printer_name: str,
) -> PrintJob:
    existing = (
        db.query(PrintJob)
        .filter(
            PrintJob.package_id == package_id,
            PrintJob.label_code == label_code,
            PrintJob.status.in_(("pending", "printing")),
        )
        .first()
    )
    if existing:
        return existing
    job = PrintJob(
        package_id=package_id,
        label_code=label_code,
        printer_name=printer_name,
        status="pending",
    )
    db.add(job)
    db.flush()
    return job


def queue_print_for_label(
    db: Session,
    label: PackageLabel,
    pkg: MesJobPackage,
    *,
    username: str,
    try_network_print: bool = True,
) -> PrintJob | None:
    printer = resolve_printer_for_job(db)
    pname = printer_display_name(printer)
    print_job = create_print_job(
        db,
        package_id=pkg.id,
        label_code=label.label_code,
        printer_name=pname,
    )

    if try_network_print and printer and not _printer_uses_cloud_agent(printer):
        try:
            job = pkg.job or db.query(MesProductionJob).filter(MesProductionJob.id == pkg.job_id).first()
            template = job.template if job else None
            meta = label_meta_from_package(pkg, job, template)
            sent = print_package_label(db, label, package_meta=meta, printer=printer)
            if sent:
                now = datetime.utcnow()
                print_job.status = "completed"
                print_job.printed_at = now
                label.printed_at = now
                label.printer_name = sent
        except Exception as exc:
            print_job.status = "failed"
            print_job.error_message = str(exc)[:500]

    return print_job


def list_pending_jobs(db: Session, *, printer_name: str | None = None) -> list[PrintJob]:
    q = db.query(PrintJob).filter(PrintJob.status == "pending")
    if printer_name:
        q = q.filter(PrintJob.printer_name == printer_name)
    return q.order_by(PrintJob.created_at.asc()).limit(50).all()


def get_print_job(db: Session, job_id: int) -> PrintJob | None:
    return (
        db.query(PrintJob)
        .options(joinedload(PrintJob.package).joinedload(MesJobPackage.job).joinedload(MesProductionJob.template))
        .filter(PrintJob.id == job_id)
        .first()
    )


def start_print_job(db: Session, job_id: int) -> PrintJob:
    job = get_print_job(db, job_id)
    if not job:
        raise ValueError("Print job not found")
    if job.status not in ("pending", "failed"):
        raise ValueError(f"Job cannot start (status: {job.status})")
    job.status = "printing"
    job.error_message = ""
    return job


def complete_print_job(db: Session, job_id: int) -> PrintJob:
    job = get_print_job(db, job_id)
    if not job:
        raise ValueError("Print job not found")
    if job.status not in ("printing", "pending"):
        raise ValueError(f"Job cannot complete (status: {job.status})")
    now = datetime.utcnow()
    job.status = "completed"
    job.printed_at = now
    job.error_message = ""
    label = db.query(PackageLabel).filter(PackageLabel.package_id == job.package_id).first()
    if label:
        label.printed_at = now
        label.printer_name = job.printer_name
    return job


def fail_print_job(db: Session, job_id: int, error_message: str) -> PrintJob:
    job = get_print_job(db, job_id)
    if not job:
        raise ValueError("Print job not found")
    job.status = "failed"
    job.error_message = (error_message or "Print failed")[:2000]
    return job


def retry_print_job(db: Session, job_id: int) -> PrintJob:
    job = get_print_job(db, job_id)
    if not job:
        raise ValueError("Print job not found")
    if job.status != "failed":
        raise ValueError("Only failed jobs can be retried")
    job.status = "pending"
    job.error_message = ""
    job.printed_at = None
    return job


def reprint_label(db: Session, label_code: str) -> PrintJob:
    label = db.query(PackageLabel).filter(PackageLabel.label_code == label_code.strip()).first()
    if not label:
        raise ValueError("Label not found")
    printer = resolve_printer_for_job(db)
    return create_print_job(
        db,
        package_id=label.package_id,
        label_code=label.label_code,
        printer_name=printer_display_name(printer),
    )


def record_agent_heartbeat(
    db: Session,
    *,
    printer_name: str,
    hostname: str = "",
    agent_version: str = "",
) -> PrintAgentHeartbeat:
    row = db.query(PrintAgentHeartbeat).filter(PrintAgentHeartbeat.printer_name == printer_name).first()
    now = datetime.utcnow()
    if not row:
        row = PrintAgentHeartbeat(printer_name=printer_name)
        db.add(row)
    row.last_seen_at = now
    row.hostname = hostname or row.hostname
    row.agent_version = agent_version or row.agent_version
    return row


def _is_agent_online(last_seen: datetime | None) -> bool:
    if not last_seen:
        return False
    return (datetime.utcnow() - last_seen).total_seconds() <= AGENT_ONLINE_SECONDS


def build_label_bytes_for_job(db: Session, job: PrintJob) -> bytes:
    pkg = job.package or db.query(MesJobPackage).filter(MesJobPackage.id == job.package_id).first()
    prod_job = pkg.job if pkg else None
    template = prod_job.template if prod_job else None
    meta = label_meta_from_package(pkg, prod_job, template) if pkg else {}
    company = get_settings_group(db, "company").get("company_name", "AZMUS FURNITURE")
    return build_label_png_bytes(
        company=company or "AZMUS FURNITURE",
        label_code=job.label_code,
        product=meta.get("product_name") or meta.get("product_code") or "—",
        weight_kg=float(meta.get("net_weight_kg") or 0),
        quantity=int(meta.get("quantity") or 1),
    )


def serialize_print_job(job: PrintJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "package_id": job.package_id,
        "label_code": job.label_code,
        "printer_name": job.printer_name,
        "status": job.status,
        "created_at": job.created_at,
        "printed_at": job.printed_at,
        "error_message": job.error_message or "",
    }


def printing_dashboard(db: Session) -> dict[str, Any]:
    printers_cfg = get_printers_config(db)
    heartbeats = {h.printer_name: h for h in db.query(PrintAgentHeartbeat).all()}
    now = datetime.utcnow()
    printer_rows = []
    for p in printers_cfg:
        pname = printer_display_name(p)
        hb = heartbeats.get(pname)
        last_seen = hb.last_seen_at if hb else None
        last_completed = (
            db.query(PrintJob)
            .filter(PrintJob.printer_name == pname, PrintJob.status == "completed")
            .order_by(PrintJob.printed_at.desc())
            .first()
        )
        pending_count = (
            db.query(PrintJob)
            .filter(PrintJob.printer_name == pname, PrintJob.status == "pending")
            .count()
        )
        failed_count = (
            db.query(PrintJob)
            .filter(PrintJob.printer_name == pname, PrintJob.status == "failed")
            .count()
        )
        printer_rows.append(
            {
                "name": pname,
                "brand": p.get("brand", ""),
                "connection_type": p.get("connection_type", "cloud_agent"),
                "windows_printer_name": p.get("windows_printer_name", ""),
                "online": _is_agent_online(last_seen),
                "last_seen_at": last_seen,
                "hostname": hb.hostname if hb else "",
                "last_print_at": last_completed.printed_at if last_completed else None,
                "last_print_label": last_completed.label_code if last_completed else None,
                "queue_count": pending_count,
                "failed_count": failed_count,
            }
        )

    recent_failed = (
        db.query(PrintJob)
        .filter(PrintJob.status == "failed")
        .order_by(PrintJob.created_at.desc())
        .limit(20)
        .all()
    )
    return {
        "printers": printer_rows,
        "failed_jobs": [serialize_print_job(j) for j in recent_failed],
        "totals": {
            "pending": db.query(PrintJob).filter(PrintJob.status == "pending").count(),
            "printing": db.query(PrintJob).filter(PrintJob.status == "printing").count(),
            "failed": db.query(PrintJob).filter(PrintJob.status == "failed").count(),
            "completed_today": db.query(PrintJob)
            .filter(
                PrintJob.status == "completed",
                PrintJob.printed_at >= datetime.combine(now.date(), datetime.min.time()),
            )
            .count(),
        },
    }
