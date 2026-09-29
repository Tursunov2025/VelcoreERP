"""Explicit repair for unambiguous migrated Painting completion records."""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from models import MesProductionJob, ProjectLineBomSnapshot
from services.audit import log_value_change
from services.project_execution import _linked_operation_quantity, _qc_preceding_stage, record_absolute_operation


def reconcile_qc_predecessors(db: Session, *, job_id: int | None = None,
                              dry_run: bool = True, actor: str = "qc-reconciliation", reason: str = "") -> dict:
    reconciliation_reason = reason.strip()
    query = db.query(MesProductionJob).options(
        joinedload(MesProductionJob.bom_lines), joinedload(MesProductionJob.route_steps)
    ).filter(MesProductionJob.project_id.isnot(None))
    if job_id is not None:
        query = query.filter(MesProductionJob.id == job_id)
    result = {"dry_run": dry_run, "jobs_scanned": 0, "eligible": 0, "applied": 0, "refused": 0, "rows": []}
    for job in query.order_by(MesProductionJob.id):
        result["jobs_scanned"] += 1
        stage_kind, step = _qc_preceding_stage(job)
        if stage_kind != "painting" or not step or not step.completed_at:
            continue
        for line in job.bom_lines or []:
            refusal_reason = None
            candidate = min(float(line.allocated_quantity or 0), float(line.painted_quantity or 0))
            existing = max(float(line.paint_accepted_quantity or 0), _linked_operation_quantity(db, job, line, "painting_accepted"))
            snapshot = db.get(ProjectLineBomSnapshot, line.project_line_bom_snapshot_id) if line.project_line_bom_snapshot_id else None
            if existing > 0:
                continue
            if not all((job.project_id, job.project_line_id, job.project_release_snapshot_id, line.project_line_bom_snapshot_id)):
                refusal_reason = "missing_project_linkage"
            elif not snapshot or snapshot.release_id != job.project_release_snapshot_id or snapshot.project_line_id != job.project_line_id:
                refusal_reason = "snapshot_linkage_mismatch"
            elif candidate <= 0 or candidate < float(line.allocated_quantity or 0) - 0.0001:
                refusal_reason = "painting_completion_incomplete"
            elif float(line.paint_rejected_quantity or 0) > 0:
                refusal_reason = "painting_rejection_requires_review"
            elif float(line.accepted_quantity or 0) + 0.0001 < candidate:
                refusal_reason = "svarka_predecessor_insufficient"
            row = {"job_id": job.id, "job_line_id": line.id, "candidate_quantity": candidate,
                   "diagnostic_code": "QC-RECONCILE-PAINT-ACCEPTANCE", "reason": refusal_reason or "eligible"}
            result["rows"].append(row)
            if refusal_reason:
                result["refused"] += 1
                continue
            result["eligible"] += 1
            if dry_run:
                continue
            old = float(line.paint_accepted_quantity or 0)
            line.paint_accepted_quantity = candidate
            log_value_change(db, actor, "qc_predecessor_reconcile", "mes_job_bom_line", line.id,
                             "paint_accepted_quantity", old, candidate)
            record_absolute_operation(
                db, job, operation_type="painting_accepted", absolute_quantity=candidate,
                username=actor, terminal="qc_reconciliation", job_line=line, route_step=step,
                accepted=candidate, source_record_type="qc_predecessor_reconciliation",
                notes=f"QC-RECONCILE-PAINT-ACCEPTANCE: {reconciliation_reason}".rstrip(": "),
            )
            result["applied"] += 1
    return result
