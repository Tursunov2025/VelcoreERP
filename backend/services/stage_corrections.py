"""Quantity-safe corrections in the canonical project execution ledger."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from models import (
    MesDispatchPackage, MesFinishedGoodsInventory, MesJobBomLine, MesJobPackage,
    MesJobRework, MesProductionJob, ProjectProductionOperation,
)
from services.audit import log_action
from services.project_execution import synchronize_project


class StageCorrectionError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(message); self.code = code; self.message = message; self.status_code = status_code


RETURN_TYPES = {
    ("qc", "painting"): "qc_return_to_painting",
    ("packaging", "qc"): "packaging_return_to_qc",
    ("painting", "svarka"): "painting_return_to_svarka",
    ("svarka", "lazer"): "svarka_return_to_lazer",
}
REASONS = {"incorrect_completion", "quality_issue", "repaint", "reweld", "incorrect_quantity", "operator_error", "other"}


def _job(db: Session, job_id: int) -> MesProductionJob:
    row = db.query(MesProductionJob).with_for_update().options(
        joinedload(MesProductionJob.bom_lines), joinedload(MesProductionJob.route_steps)
    ).filter_by(id=job_id).first()
    if not row or not row.project_id:
        raise StageCorrectionError("project_job_not_found", "Project-linked MES job not found", 404)
    return row


def _downstream_quantity(db: Session, job_id: int) -> float:
    packaged = float(db.query(func.coalesce(func.sum(MesJobPackage.quantity), 0)).filter(
        MesJobPackage.job_id == job_id, MesJobPackage.status != "cancelled").scalar() or 0)
    inventory = float(db.query(func.coalesce(func.sum(MesFinishedGoodsInventory.quantity), 0)).filter(
        MesFinishedGoodsInventory.job_id == job_id).scalar() or 0)
    dispatch = float(db.query(func.coalesce(func.sum(MesJobPackage.quantity), 0)).join(
        MesDispatchPackage, MesDispatchPackage.package_id == MesJobPackage.id).filter(
        MesJobPackage.job_id == job_id).scalar() or 0)
    return max(packaged, inventory, dispatch)


def _recorded(db: Session, line_id: int, kind: str) -> float:
    return float(db.query(func.coalesce(func.sum(ProjectProductionOperation.quantity), 0)).filter_by(
        job_line_id=line_id, operation_type=kind).scalar() or 0)


def return_stage(db: Session, *, job_id: int, job_line_id: int, source_stage: str,
                 destination_stage: str, quantity: float, reason_code: str, comment: str,
                 operation_key: str, actor: str) -> dict:
    source_stage=source_stage.lower(); destination_stage=destination_stage.lower()
    kind=RETURN_TYPES.get((source_stage,destination_stage))
    if not kind: raise StageCorrectionError("stage_return_not_allowed", "Requested backward stage transition is not allowed")
    if reason_code not in REASONS: raise StageCorrectionError("stage_return_reason_required", "A valid return reason is required", 422)
    if quantity <= 0: raise StageCorrectionError("stage_return_quantity_invalid", "Return quantity must be positive", 422)
    existing=db.query(ProjectProductionOperation).filter_by(idempotency_key=operation_key).first()
    if existing:
        if existing.operation_type != kind or abs(existing.quantity-float(quantity)) > .0001:
            raise StageCorrectionError("stage_return_idempotency_conflict", "Operation key was used for another return")
        return {"id":existing.id,"idempotent":True,"quantity":existing.quantity,"operation_type":existing.operation_type}
    job=_job(db,job_id); line=db.query(MesJobBomLine).with_for_update().filter_by(id=job_line_id,job_id=job.id).first()
    if not line: raise StageCorrectionError("job_bom_line_not_found", "MES BOM line not found", 404)
    if _downstream_quantity(db,job.id)>0:
        raise StageCorrectionError("stage_return_downstream_locked", "Downstream packaging, warehouse or shipment evidence blocks this return")
    already=_recorded(db,line.id,kind)
    if kind=="qc_return_to_painting": available=max(0.0,float(line.qc_accepted_quantity or 0)+float(line.qc_rework_quantity or 0)-already)
    elif kind=="painting_return_to_svarka": available=max(0.0,float(line.paint_accepted_quantity or 0)-already)
    elif kind=="svarka_return_to_lazer": available=max(0.0,float(line.accepted_quantity or 0)-already)
    else: available=max(0.0,float(line.qc_accepted_quantity or 0)-already)
    if quantity > available+.0001:
        raise StageCorrectionError("stage_return_quantity_exceeds_available", "Return quantity exceeds the safely available quantity")
    now=datetime.utcnow()
    returned_rework=0.0; returned_accepted=float(quantity)
    if kind=="qc_return_to_painting":
        returned_rework=min(float(quantity),float(line.qc_rework_quantity or 0)); returned_accepted=float(quantity)-returned_rework
    event=ProjectProductionOperation(project_id=job.project_id,release_id=job.project_release_snapshot_id,
        project_line_id=job.project_line_id,job_id=job.id,job_line_id=line.id,operation_type=kind,
        result="returned",quantity=float(quantity),accepted_quantity=returned_accepted,rework_quantity=returned_rework,operator=actor,
        terminal="stage_correction",source_record_type="stage_return",source_record_id=line.id,
        source_version=operation_key,idempotency_key=operation_key,occurred_at=now,notes=comment,
        source_stage=source_stage,destination_stage=destination_stage,reason_code=reason_code,comment=comment)
    db.add(event); db.flush()
    if kind=="qc_return_to_painting":
        # The append-only event is authoritative; these columns are projections
        # consumed by the existing terminals and are reduced only with evidence.
        remaining=float(quantity); take=min(remaining,float(line.qc_rework_quantity or 0)); line.qc_rework_quantity-=take; remaining-=take
        line.qc_accepted_quantity=max(0.0,float(line.qc_accepted_quantity or 0)-remaining)
        db.add(MesJobRework(job_id=job.id,bom_line_id=line.id,quantity=float(quantity),status="pending",
            notes=f"{reason_code}: {comment}".strip(),created_by=actor))
    elif kind=="painting_return_to_svarka": line.paint_accepted_quantity=max(0.0,float(line.paint_accepted_quantity or 0)-float(quantity))
    elif kind=="svarka_return_to_lazer": line.accepted_quantity=max(0.0,float(line.accepted_quantity or 0)-float(quantity))
    synchronize_project(db,job.project_id)
    # A compensated quantity is physically back in production even when an
    # older project lacks complete snapshot evidence for percentage rebuild.
    job.status="in_progress"
    if job.project_line: job.project_line.status="in_production"
    if job.project and job.project.status not in {"cancelled"}: job.project.status="in_production"
    log_action(db,actor,"stage_return","mes_production_job",job.id,f"{source_stage}->{destination_stage};qty={quantity};reason={reason_code}")
    return {"id":event.id,"idempotent":False,"quantity":event.quantity,"operation_type":kind,
            "project_id":job.project_id,"project_line_id":job.project_line_id,"job_id":job.id,"job_line_id":line.id}


def reopen_stage(db: Session, *, job_id: int, stage: str, reason_code: str, comment: str,
                 operation_key: str, actor: str) -> dict:
    if reason_code not in REASONS: raise StageCorrectionError("stage_return_reason_required", "A valid reopen reason is required", 422)
    existing=db.query(ProjectProductionOperation).filter_by(idempotency_key=operation_key).first()
    if existing: return {"id":existing.id,"idempotent":True}
    job=_job(db,job_id)
    if _downstream_quantity(db,job.id)>0: raise StageCorrectionError("stage_reopen_downstream_locked", "Downstream evidence blocks reopening this stage")
    needle=stage.lower(); step=next((s for s in job.route_steps if needle in str(s.stage_name or "").lower()),None)
    if not step or not step.completed_at: raise StageCorrectionError("stage_not_completed", "Completed stage was not found")
    original=step.completed_at; now=datetime.utcnow()
    event=ProjectProductionOperation(project_id=job.project_id,release_id=job.project_release_snapshot_id,
        project_line_id=job.project_line_id,job_id=job.id,route_step_id=step.id,stage_id=step.stage_id,
        operation_type="stage_reopened",result="reopened",quantity=float(job.quantity or 1),operator=actor,
        terminal="stage_correction",source_record_type="mes_job_route_step",source_record_id=step.id,
        source_version=operation_key,idempotency_key=operation_key,occurred_at=now,notes=comment,
        source_stage=stage.lower(),destination_stage=stage.lower(),reason_code=reason_code,comment=comment,
        original_completed_at=original,reopened_at=now,reopened_by=actor)
    db.add(event); step.completed_at=None; job.status="in_progress"; db.flush(); synchronize_project(db,job.project_id)
    log_action(db,actor,"stage_reopen","mes_job_route_step",step.id,f"stage={stage};reason={reason_code}")
    return {"id":event.id,"idempotent":False,"route_step_id":step.id,"original_completed_at":original,"reopened_at":now}


def correction_history(db: Session, job_id: int) -> list[dict]:
    rows=db.query(ProjectProductionOperation).filter(ProjectProductionOperation.job_id==job_id,
        ProjectProductionOperation.operation_type.in_(list(RETURN_TYPES.values())+["stage_reopened"])).order_by(ProjectProductionOperation.occurred_at).all()
    return [{"id":x.id,"type":x.operation_type,"source_stage":x.source_stage,"destination_stage":x.destination_stage,
        "quantity":x.quantity,"reason_code":x.reason_code,"comment":x.comment,"actor":x.operator,
        "occurred_at":x.occurred_at,"original_completed_at":x.original_completed_at} for x in rows]
