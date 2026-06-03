"""Cloud print queue API for local Windows print agents."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.deps import get_current_user, require_admin
from auth.print_agent import require_print_agent
from database import get_db
from models import User
from services.print_jobs import (
    build_label_bytes_for_job,
    complete_print_job,
    fail_print_job,
    get_print_job,
    list_pending_jobs,
    printing_dashboard,
    record_agent_heartbeat,
    reprint_label,
    retry_print_job,
    serialize_print_job,
    start_print_job,
)

router = APIRouter(tags=["printing"])
admin_router = APIRouter(tags=["printing-admin"])


class PrintFailedBody(BaseModel):
    error_message: str = ""


class AgentHeartbeatBody(BaseModel):
    printer_name: str
    hostname: str = ""
    agent_version: str = "1.0.0"


@router.get("/printing/jobs/pending")
def get_pending_print_jobs(
    printer_name: Optional[str] = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_print_agent),
):
    jobs = list_pending_jobs(db, printer_name=printer_name)
    return {
        "jobs": [
            {
                **serialize_print_job(j),
                "label_url": f"/printing/jobs/{j.id}/label.png",
            }
            for j in jobs
        ]
    }


@router.get("/printing/jobs/{job_id}/label.png")
def download_label_png(
    job_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_print_agent),
):
    job = get_print_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Print job not found")
    try:
        data = build_label_bytes_for_job(db, job)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(content=data, media_type="image/png")


@router.post("/printing/jobs/{job_id}/start")
def api_start_print_job(
    job_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_print_agent),
):
    try:
        job = start_print_job(db, job_id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return serialize_print_job(job)


@router.post("/printing/jobs/{job_id}/complete")
def api_complete_print_job(
    job_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_print_agent),
):
    try:
        job = complete_print_job(db, job_id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return serialize_print_job(job)


@router.post("/printing/jobs/{job_id}/failed")
def api_fail_print_job(
    job_id: int,
    body: PrintFailedBody,
    db: Session = Depends(get_db),
    _: None = Depends(require_print_agent),
):
    try:
        job = fail_print_job(db, job_id, body.error_message)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return serialize_print_job(job)


@router.post("/printing/agent/heartbeat")
def agent_heartbeat(
    body: AgentHeartbeatBody,
    db: Session = Depends(get_db),
    _: None = Depends(require_print_agent),
):
    if not body.printer_name.strip():
        raise HTTPException(status_code=400, detail="printer_name is required")
    record_agent_heartbeat(
        db,
        printer_name=body.printer_name.strip(),
        hostname=body.hostname,
        agent_version=body.agent_version,
    )
    db.commit()
    return {"ok": True}


@admin_router.get("/admin/printing/dashboard")
def admin_printing_dashboard(
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
):
    return printing_dashboard(db)


@admin_router.post("/printing/jobs/{job_id}/retry")
def admin_retry_print_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    try:
        job = retry_print_job(db, job_id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return serialize_print_job(job)


@admin_router.post("/packages/{label_code}/reprint")
def admin_reprint_label(
    label_code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from services.permissions import user_has_permission

    if user.role != "admin" and not user_has_permission(db, user, "mes_view"):
        raise HTTPException(status_code=403, detail="Permission required")
    try:
        job = reprint_label(db, label_code)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return serialize_print_job(job)
