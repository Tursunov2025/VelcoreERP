from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import (
    MaterialReservation, MesDispatch, MesDispatchPackage, MesFinishedGoodsInventory,
    MesJobBomLine, MesJobPackage, MesJobRework, MesProductionJob, MesTrip, ProductionProject,
    ProductionProjectLine, ProjectDetailRequirement, ProjectLineBomSnapshot,
    ProjectProductionOperation, ProjectReleaseSnapshot, ProjectStockAllocation, MesShipmentItem,
)


class ExecutionError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message); self.code = code


def _recorded_job_line_quantity(db: Session, job_line_id: int, operation_type: str) -> float:
    return float(db.query(func.coalesce(func.sum(ProjectProductionOperation.quantity), 0)).filter_by(
        job_line_id=job_line_id, operation_type=operation_type,
    ).scalar() or 0)


def _linked_operation_quantity(db: Session, job: MesProductionJob, job_line: MesJobBomLine,
                               operation_type: str) -> float:
    """Sum only evidence belonging to the same released job/line identity."""
    query = db.query(func.coalesce(func.sum(ProjectProductionOperation.quantity), 0)).filter(
        ProjectProductionOperation.job_id == job.id,
        ProjectProductionOperation.job_line_id == job_line.id,
        ProjectProductionOperation.operation_type == operation_type,
    )
    if job.project_id:
        query = query.filter(
            ProjectProductionOperation.project_id == job.project_id,
            ProjectProductionOperation.project_line_id == job.project_line_id,
            ProjectProductionOperation.release_id == job.project_release_snapshot_id,
        )
    return float(query.scalar() or 0)


def _effective_stock_readiness(db: Session, job: MesProductionJob, job_line: MesJobBomLine) -> float:
    """Return reusable stock assigned to this released job line.

    Released allocations are excluded, while consumed stock remains valid
    readiness.  The line-level snapshot caps the aggregate allocation so
    stock reserved for another project/detail cannot be counted here.
    """
    allocated = float(job_line.stock_reserved_quantity or 0)
    if allocated <= 0 or not job.project_id:
        return max(0.0, allocated)
    allocations = db.query(ProjectStockAllocation).join(ProjectDetailRequirement).filter(
        ProjectStockAllocation.project_id == job.project_id,
        ProjectStockAllocation.release_id == job.project_release_snapshot_id,
        ProjectDetailRequirement.detail_id == job_line.part_id,
    ).all()
    if not allocations:
        return max(0.0, allocated)
    effective = sum(max(0.0, float(a.reserved_quantity or 0) - float(a.released_quantity or 0)) for a in allocations)
    return max(0.0, min(allocated, effective))


def _qc_preceding_stage(job: MesProductionJob):
    required = [step for step in sorted(job.route_steps or [], key=lambda row: (row.step_order, row.id)) if step.is_required]
    qc_index = next((index for index, step in enumerate(required)
                     if "nazorat" in str(step.stage_name or "").lower() or "qc" in str(step.stage_name or "").lower()), len(required))
    for step in reversed(required[:qc_index]):
        name = str(step.stage_name or "").lower()
        if any(token in name for token in ("kraska", "paint", "bo'y")): return "painting", step
        if any(token in name for token in ("svar", "weld")): return "svarka", step
        if any(token in name for token in ("lazer", "laser", "kesish", "cut")): return "lazer", step
    return "legacy", None


def qc_predecessor_fact(db: Session, job: MesProductionJob, job_line: MesJobBomLine) -> dict:
    """One source policy shared by QC reads and writes; this function never mutates."""
    allocated = float(job_line.allocated_quantity or 0)
    stage_kind, step = _qc_preceding_stage(job)
    stage_name = step.stage_name if step else "Legacy"
    diagnostic_code = None
    blocking_reason = None

    if stage_kind == "painting":
        column_value = float(job_line.paint_accepted_quantity or 0) if job.project_id else float(job_line.accepted_quantity or 0)
        evidence_value = _linked_operation_quantity(db, job, job_line, "painting_accepted") if job.project_id else 0.0
        completed = max(column_value, evidence_value)
        source = "painting_accepted"
        if completed <= 0 and step and step.completed_at and float(job_line.painted_quantity or 0) > 0:
            diagnostic_code = "QC-RECONCILE-PAINT-ACCEPTANCE"
            blocking_reason = "predecessor_reconciliation_required"
    elif stage_kind == "svarka":
        column_value = float(job_line.accepted_quantity or 0)
        evidence_value = _linked_operation_quantity(db, job, job_line, "svarka_accepted") if job.project_id else 0.0
        completed = max(column_value, evidence_value)
        source = "svarka_accepted"
    elif stage_kind == "lazer":
        stock = _effective_stock_readiness(db, job, job_line)
        column_value = float(job_line.completed_quantity or 0) + stock
        evidence_value = (_linked_operation_quantity(db, job, job_line, "lazer_completed") if job.project_id else 0.0) + stock
        completed = max(column_value, evidence_value)
        source = "lazer_or_stock_ready"
    else:
        # Old standalone records without a recognizable route retain their
        # historical allocation source; routed standalone jobs use the stage above.
        column_value = allocated
        evidence_value = 0.0
        completed = allocated
        source = "legacy_allocation"
    completed = min(allocated, max(0.0, completed))
    if completed <= 0 and not blocking_reason:
        blocking_reason = "predecessor_not_completed"
    return {
        "quantity": completed,
        "source": source,
        "stage_name": stage_name,
        "stage_reported_quantity": min(allocated, max(0.0, max(column_value, evidence_value))),
        "blocking_reason": blocking_reason,
        "diagnostic_code": diagnostic_code,
    }


def qc_predecessor_quantity(db: Session, job: MesProductionJob, job_line: MesJobBomLine) -> tuple[float, str]:
    """Return the completed quantity QC may disposition for one BOM detail.

    MES BOM stage quantities are authoritative.  The append-only project
    operation ledger remains a compatibility/audit source for records created
    before the stage-specific BOM columns were synchronized.
    """
    fact = qc_predecessor_fact(db, job, job_line)
    return fact["quantity"], fact["source"]


def ensure_project_active(job: MesProductionJob) -> None:
    if job.project_id and job.project and job.project.status == "cancelled":
        raise ExecutionError("project_cancelled", "Cancelled project cannot accept terminal work")


def record_absolute_operation(db: Session, job: MesProductionJob, *, operation_type: str,
                              absolute_quantity: float, username: str, terminal: str,
                              job_line: MesJobBomLine | None = None, route_step=None,
                              result: str = "completed", accepted: float = 0,
                              rejected: float = 0, rework: float = 0,
                              source_record_type: str = "mes_job_bom_line", notes: str = ""):
    if not job.project_id:
        return None
    ensure_project_active(job)
    absolute = float(absolute_quantity)
    prior = db.query(func.coalesce(func.sum(ProjectProductionOperation.quantity), 0)).filter(
        ProjectProductionOperation.project_id == job.project_id,
        ProjectProductionOperation.project_line_id == job.project_line_id,
        ProjectProductionOperation.job_id == job.id,
        ProjectProductionOperation.job_line_id == (job_line.id if job_line else None),
        ProjectProductionOperation.operation_type == operation_type,
    ).scalar() or 0
    if absolute < float(prior) - 0.0001:
        raise ExecutionError("quantity_exceeds_remaining", "Project execution quantities are append-only")
    delta = absolute - float(prior)
    source_id = job_line.id if job_line else (route_step.id if route_step else job.id)
    version = f"{absolute:.6f}"
    key = f"project:{job.project_id}:job:{job.id}:{operation_type}:{source_id}:{version}"
    existing = db.query(ProjectProductionOperation).filter_by(idempotency_key=key).first()
    if existing: return existing
    if delta <= 0: return None
    maximum = float(job_line.allocated_quantity or 0) if job_line else float(job.quantity or 0)
    if job_line and operation_type == "lazer_completed":
        maximum = float(job_line.production_required_quantity or 0)
    if absolute > maximum + 0.0001:
        raise ExecutionError("quantity_exceeds_remaining", "Quantity exceeds released requirement")
    if job_line:
        def recorded(kind: str) -> float:
            return float(db.query(func.coalesce(func.sum(ProjectProductionOperation.quantity), 0)).filter_by(
                job_line_id=job_line.id, operation_type=kind).scalar() or 0)
        route_names = {str(step.stage_name or "").lower() for step in job.route_steps if step.is_required}
        lazer_ready = recorded("lazer_completed") + _effective_stock_readiness(db, job, job_line)
        welding_required = any("svar" in name or "weld" in name for name in route_names)
        painting_required = any("kraska" in name or "paint" in name or "bo'y" in name for name in route_names)
        if operation_type.startswith("svarka_") and absolute > lazer_ready + 0.0001:
            raise ExecutionError("stage_dependency_not_satisfied", "Welding exceeds laser/stock readiness")
        if operation_type.startswith("painting_"):
            predecessor = recorded("svarka_accepted") if welding_required else lazer_ready
            if absolute > predecessor + 0.0001:
                raise ExecutionError("stage_dependency_not_satisfied", "Painting exceeds predecessor readiness")
        if operation_type in {"qc_approved", "qc_rejected", "rework_created"}:
            predecessor, _ = qc_predecessor_quantity(db, job, job_line)
            completed_rework_records = float(db.query(func.coalesce(func.sum(MesJobRework.quantity), 0)).filter(
                MesJobRework.job_id == job.id,
                MesJobRework.bom_line_id == job_line.id,
                MesJobRework.status == "completed",
            ).scalar() or 0)
            # Historical/canonical callers may already have an append-only
            # rework_completed operation even when no MesJobRework row exists.
            # Both are authoritative evidence of the same completed quantity;
            # use the larger projection rather than double-counting them.
            completed_rework = max(completed_rework_records, recorded("rework_completed"))
            dispositions = {
                "qc_approved": recorded("qc_approved"),
                "qc_rejected": recorded("qc_rejected"),
                "rework_created": max(0.0, recorded("rework_created") - completed_rework),
            }
            if operation_type == "rework_created":
                dispositions[operation_type] = max(0.0, absolute - completed_rework)
            else:
                dispositions[operation_type] = absolute
            if sum(dispositions.values()) > predecessor + 0.0001:
                raise ExecutionError("qc_exceeds_completed", "QC disposition exceeds completed production")
    operation = ProjectProductionOperation(
        project_id=job.project_id, release_id=job.project_release_snapshot_id,
        project_line_id=job.project_line_id, job_id=job.id,
        job_line_id=job_line.id if job_line else None,
        route_step_id=route_step.id if route_step else None,
        stage_id=route_step.stage_id if route_step else None,
        operation_type=operation_type, result=result, quantity=delta,
        accepted_quantity=max(0.0, accepted), rejected_quantity=max(0.0, rejected),
        rework_quantity=max(0.0, rework), operator=username, terminal=terminal,
        source_record_type=source_record_type, source_record_id=source_id,
        source_version=version, idempotency_key=key, notes=notes,
    )
    db.add(operation)
    try: db.flush()
    except IntegrityError as exc:
        raise ExecutionError("operation_already_recorded", "Operation was already recorded") from exc
    synchronize_project(db, job.project_id)
    return operation


def consume_project_stock(db: Session, job: MesProductionJob, detail_id: int, quantity: float, username: str | None = None) -> float:
    if not job.project_id: return 0.0
    remaining = float(quantity)
    allocations = db.query(ProjectStockAllocation).with_for_update().join(ProjectDetailRequirement).filter(
        ProjectStockAllocation.project_id == job.project_id,
        ProjectDetailRequirement.detail_id == detail_id,
    ).order_by(ProjectStockAllocation.stock_id, ProjectStockAllocation.id).all()
    consumed = 0.0
    from services.warehouse_stock import consume_reserved_stock
    for allocation in allocations:
        available = float(allocation.reserved_quantity - allocation.consumed_quantity - allocation.released_quantity)
        take = min(remaining, available)
        if take <= 0: continue
        consume_reserved_stock(
            db, allocation.stock_id, take, username or job.created_by or "system", job.id,
            f"Project {job.project.project_code} issued to job {job.job_number}",
        )
        allocation.consumed_quantity += take; allocation.requirement.consumed_quantity += take
        allocation.status = "consumed" if allocation.consumed_quantity + allocation.released_quantity >= allocation.reserved_quantity else "partially_consumed"
        remaining -= take; consumed += take
        if remaining <= 0: break
    return consumed


def _operation_equivalent(db: Session, line: ProductionProjectLine, operation_type: str) -> float:
    snapshots = db.query(ProjectLineBomSnapshot).filter_by(project_line_id=line.id).all()
    if not snapshots: return 0.0
    equivalents = []
    for snapshot in snapshots:
        job_line = db.query(MesJobBomLine).filter_by(project_line_bom_snapshot_id=snapshot.id).first()
        total = 0.0 if not job_line else db.query(func.coalesce(func.sum(ProjectProductionOperation.quantity), 0)).filter_by(
            job_line_id=job_line.id, operation_type=operation_type).scalar() or 0
        compensating_type = {"qc_approved": "qc_return_to_painting", "painting_accepted": "painting_return_to_svarka", "svarka_accepted": "svarka_return_to_lazer"}.get(operation_type)
        if job_line and compensating_type:
            amount_column = ProjectProductionOperation.accepted_quantity if compensating_type == "qc_return_to_painting" else ProjectProductionOperation.quantity
            returned = db.query(func.coalesce(func.sum(amount_column), 0)).filter_by(
                job_line_id=job_line.id, operation_type=compensating_type).scalar() or 0
            total = max(0.0, float(total) - float(returned))
        # Reusable detail stock is authoritative predecessor readiness alongside
        # LAZER production (the same rule used by qc_predecessor_fact). Without
        # this, a fully stock-covered BOM line incorrectly forces project
        # production and shipment eligibility back to zero.
        if job_line and operation_type == "lazer_completed":
            # A release allocates reusable stock per project/detail.  Count
            # only the portion still owned by this release; cancellation or a
            # release transaction must never remain visible as readiness.
            total = float(total) + _effective_stock_readiness(db, job_line.job, job_line)
        equivalents.append(float(total) / float(snapshot.source_quantity))
    return min(equivalents)


def _product_operation_quantity(db: Session, line: ProductionProjectLine, operation_type: str) -> float:
    """Product-level evidence is already expressed in finished-product units."""
    return float(db.query(func.coalesce(func.sum(ProjectProductionOperation.quantity), 0)).filter_by(
        project_line_id=line.id, operation_type=operation_type,
    ).scalar() or 0)


def reconcile_project_line(db: Session, line: ProductionProjectLine) -> dict:
    produced = min(float(line.quantity), _operation_equivalent(db, line, "lazer_completed"))
    qc_approved = min(produced, float(line.quantity), _operation_equivalent(db, line, "qc_approved"))
    qc_rejected = min(float(line.quantity), _operation_equivalent(db, line, "qc_rejected"))
    jobs = select(MesProductionJob.id).where(MesProductionJob.project_line_id == line.id)
    completed_rework_records = float(db.query(func.coalesce(func.sum(MesJobRework.quantity), 0)).filter(
        MesJobRework.job_id.in_(jobs), MesJobRework.status == "completed",
    ).scalar() or 0)
    completed_rework = max(_operation_equivalent(db, line, "rework_completed"), completed_rework_records)
    rework = min(float(line.quantity), _operation_equivalent(db, line, "rework_created") - completed_rework)
    # ProjectProductionOperation is the authoritative project packaging evidence.
    # Package rows describe physical package allocation and must never advance
    # project progress by themselves.
    packaged_evidence = _product_operation_quantity(db, line, "packaged")
    packaged_rows = db.query(func.coalesce(func.sum(MesJobPackage.quantity), 0)).filter(MesJobPackage.job_id.in_(jobs), MesJobPackage.status != "cancelled").scalar() or 0
    finished = db.query(func.coalesce(func.sum(MesFinishedGoodsInventory.quantity), 0)).filter(MesFinishedGoodsInventory.job_id.in_(jobs), MesFinishedGoodsInventory.status.in_(("in_stock", "loaded", "dispatched", "delivered"))).scalar() or 0
    loaded = db.query(func.coalesce(func.sum(MesJobPackage.quantity), 0)).join(MesDispatchPackage, MesDispatchPackage.package_id == MesJobPackage.id).filter(MesJobPackage.job_id.in_(jobs), MesDispatchPackage.status.in_(("loaded", "shipped", "delivered"))).scalar() or 0
    shipped = db.query(func.coalesce(func.sum(MesJobPackage.quantity), 0)).join(MesDispatchPackage, MesDispatchPackage.package_id == MesJobPackage.id).filter(MesJobPackage.job_id.in_(jobs), MesDispatchPackage.status.in_(("shipped", "delivered"))).scalar() or 0
    shipment_loaded = db.query(func.coalesce(func.sum(MesShipmentItem.loaded_quantity), 0)).filter(MesShipmentItem.project_line_id == line.id).scalar() or 0
    shipment_shipped = db.query(func.coalesce(func.sum(MesShipmentItem.loaded_quantity), 0)).join(MesTrip, MesTrip.id == MesShipmentItem.trip_id).filter(
        MesShipmentItem.project_line_id == line.id, MesTrip.status.in_(("dispatched", "in_transit", "delivered", "accepted"))).scalar() or 0
    delivered = db.query(func.coalesce(func.sum(MesShipmentItem.delivered_quantity), 0)).filter(MesShipmentItem.project_line_id == line.id).scalar() or 0
    accepted = db.query(func.coalesce(func.sum(MesShipmentItem.accepted_quantity), 0)).join(MesTrip, MesTrip.id == MesShipmentItem.trip_id).filter(
        MesShipmentItem.project_line_id == line.id, MesTrip.status == "accepted").scalar() or 0
    loaded = max(float(loaded), float(shipment_loaded)); shipped = max(float(shipped), float(shipment_shipped))
    qc_eligible = max(0.0, qc_approved - max(0.0, rework))
    packaged = min(float(line.quantity), float(packaged_evidence), float(packaged_rows), qc_eligible, produced)
    finished = min(float(finished), packaged); loaded = min(float(loaded), finished); shipped = min(float(shipped), loaded)
    line.produced_quantity = produced; line.quality_approved_quantity = qc_approved; line.packaged_quantity = packaged; line.shipped_quantity = shipped
    line.delivered_quantity = min(float(line.quantity), float(delivered)); line.accepted_quantity = min(float(line.quantity), float(accepted))
    if shipped >= line.quantity: status = "shipped"
    elif packaged >= line.quantity: status = "ready_to_ship"
    elif produced > 0 or qc_approved > 0: status = "in_production"
    else: status = "released"
    line.status = status
    return {"project_line_id": line.id, "required_quantity": float(line.quantity), "production_started": produced > 0,
            "produced_quantity": produced, "qc_pending_quantity": max(0.0, produced - qc_approved - qc_rejected),
            "qc_approved_quantity": qc_approved, "qc_rejected_quantity": qc_rejected,
            "rework_pending_quantity": max(0.0, rework), "packaged_quantity": packaged,
            "finished_goods_quantity": finished, "loaded_quantity": loaded, "shipped_quantity": shipped,
            "delivered_quantity": line.delivered_quantity, "accepted_quantity": line.accepted_quantity,
            "remaining_quantity": max(0.0, float(line.quantity) - shipped), "status": status}


def synchronize_project(db: Session, project_id: int) -> dict:
    project = db.query(ProductionProject).with_for_update().filter_by(id=project_id).first()
    if not project or project.status == "cancelled": return {}
    facts = [reconcile_project_line(db, line) for line in project.lines]
    if project.status == "completed":
        return {"project": project, "lines": facts}
    if facts and all(item["shipped_quantity"] >= item["required_quantity"] for item in facts): project.status = "shipped"
    elif facts and all(item["packaged_quantity"] >= item["required_quantity"] for item in facts): project.status = "ready_to_ship"
    elif any(item["packaged_quantity"] > 0 for item in facts): project.status = "partially_ready"
    elif any(item["produced_quantity"] > 0 for item in facts): project.status = "in_production"
    elif project.status not in {"draft", "planned"}: project.status = "released"
    project.updated_at = datetime.utcnow(); return {"project": project, "lines": facts}


STAGE_WEIGHTS = {"production": 0.45, "quality": 0.20, "packaging": 0.15, "warehouse": 0.10, "shipping": 0.10}


def project_progress(db: Session, project: ProductionProject) -> dict:
    synced = synchronize_project(db, project.id); facts = synced.get("lines", [])
    total = sum(item["required_quantity"] for item in facts) or 1.0
    stage_values = {
        "production": sum(item["produced_quantity"] for item in facts) / total,
        "quality": sum(item["qc_approved_quantity"] for item in facts) / total,
        "packaging": sum(item["packaged_quantity"] for item in facts) / total,
        "warehouse": sum(item["finished_goods_quantity"] for item in facts) / total,
        "shipping": sum(item["shipped_quantity"] for item in facts) / total,
    }
    weighted = sum(min(1.0, stage_values[key]) * weight for key, weight in STAGE_WEIGHTS.items()) * 100
    requirements = db.query(ProjectDetailRequirement).join(ProjectReleaseSnapshot).filter(ProjectReleaseSnapshot.project_id == project.id).all()
    blockers = []
    if stage_values["production"] < 1.0 - 0.0001:
        for req in requirements:
            if req.production_required_quantity > 0:
                blockers.append({"code": "detail_production_required", "detail_id": req.detail_id, "quantity": req.production_required_quantity})
    latest = db.query(func.max(ProjectProductionOperation.occurred_at)).filter_by(project_id=project.id).scalar()
    return {"project_id": project.id, "status": project.status, "overall_progress_percent": round(weighted, 2),
            "formula": {"weights": STAGE_WEIGHTS}, "lines": facts,
            "departments": [{"stage": key, "completed_quantity": round(stage_values[key] * total, 4), "required_quantity": total, "progress_percent": round(min(1.0, stage_values[key]) * 100, 2)} for key in STAGE_WEIGHTS],
            "blocking_reasons": blockers, "stock_coverage": {"gross_required": sum(r.gross_required_quantity for r in requirements), "reserved": sum(r.stock_reserved_quantity for r in requirements), "production_required": sum(r.production_required_quantity for r in requirements)},
            "latest_activity_at": latest}


def project_forecast(db: Session, project: ProductionProject) -> dict:
    progress = project_progress(db, project)
    operations = db.query(ProjectProductionOperation).filter_by(project_id=project.id).order_by(ProjectProductionOperation.occurred_at).all()
    blockers = progress["blocking_reasons"]
    reasons = []
    if blockers: reasons.append("material_or_detail_shortage")
    evidence_span = ((operations[-1].occurred_at - operations[0].occurred_at).total_seconds() / 86400) if len(operations) >= 2 else 0
    if len(operations) < 5 or evidence_span < 1: reasons.append("forecast_insufficient_data")
    if reasons:
        classification = "at_risk" if project.required_delivery_date and blockers else "unavailable"
        return {"available": False, "classification": classification, "confidence": "insufficient",
                "earliest_completion": None, "latest_completion": None, "critical_blocking_stage": "production" if blockers else None,
                "blockers": blockers, "delayed_product_lines": [], "reason_codes": reasons,
                "evidence_window_days": None, "sample_size": len(operations)}
    first, last = operations[0].occurred_at, operations[-1].occurred_at
    elapsed_days = max((last - first).total_seconds() / 86400, 1.0)
    completed_fraction = progress["overall_progress_percent"] / 100
    if completed_fraction <= 0: return {"available": False, "classification": "unavailable", "reason_codes": ["forecast_insufficient_data"], "sample_size": len(operations)}
    remaining_days = elapsed_days * (1 - completed_fraction) / completed_fraction
    earliest = last + timedelta(days=max(1, remaining_days * 0.75)); latest = last + timedelta(days=max(1, remaining_days * 1.5))
    classification = "on_time" if not project.required_delivery_date or latest <= project.required_delivery_date else ("at_risk" if earliest <= project.required_delivery_date else "late")
    return {"available": True, "classification": classification, "confidence": "limited", "earliest_completion": earliest,
            "latest_completion": latest, "critical_blocking_stage": None, "blockers": [], "delayed_product_lines": [],
            "reason_codes": [], "evidence_window_days": round(elapsed_days, 1), "sample_size": len(operations)}
