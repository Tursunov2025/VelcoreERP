from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from constants import MES_JOB_PRIORITIES, PRODUCTION_PROJECT_TRANSITIONS
from models import (
    AuditLog, MesBomLine, MesJobBomLine, MesProductionJob, MesProductTemplate,
    ProductionProject, ProductionProjectLine, ProjectDetailRequirement,
    ProjectLineBomSnapshot, ProjectReleaseSnapshot, ProjectStockAllocation,
    WarehouseStock, WarehouseTransaction,
)
from services.audit import log_action
from services.mes_bom import active_bom_lines
from services.mes_jobs import release_job_snapshot
from services.warehouse_stock import change_stock


EDITABLE = {"draft", "planned"}


class ProjectError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, context: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.context = context or {}

    def payload(self) -> dict:
        return {"code": self.code, "message": self.message, **self.context}


def _priority(value: str) -> str:
    normalized = (value or "normal").strip().lower()
    if normalized not in MES_JOB_PRIORITIES:
        raise ProjectError("invalid_priority", "Invalid project priority")
    return normalized


def _editable(project: ProductionProject) -> None:
    if project.status not in EDITABLE:
        raise ProjectError("project_locked", "Only draft or planned projects may be edited", 409)


def _version(entity, expected: int) -> None:
    if entity.version != expected:
        raise ProjectError("project_version_conflict", "The project was changed by another user", 409, {"current_version": entity.version})


def _transition(project: ProductionProject, target: str) -> None:
    target = (target or "").strip().lower()
    if target not in PRODUCTION_PROJECT_TRANSITIONS.get(project.status, set()):
        raise ProjectError("invalid_project_transition", f"Cannot transition from {project.status} to {target}", 409)
    project.status = target


def load_project(db: Session, project_id: int, lock: bool = False) -> ProductionProject | None:
    query = db.query(ProductionProject).options(
        selectinload(ProductionProject.lines).selectinload(ProductionProjectLine.product)
    ).filter(ProductionProject.id == project_id)

    if lock:
        query = query.with_for_update()

    return query.first()


def serialize_line(line: ProductionProjectLine) -> dict:
    return {
        "id": line.id, "project_id": line.project_id, "product_id": line.product_id,
        "product_code": line.product.code if line.product else None,
        "product_name": line.product.name if line.product else None,
        "quantity": float(line.quantity), "line_reference": line.line_reference or "",
        "priority": line.priority, "required_date_override": line.required_date_override,
        "notes": line.notes or "", "status": line.status, "version": line.version,
        "produced_quantity": float(line.produced_quantity or 0),
        "quality_approved_quantity": float(line.quality_approved_quantity or 0),
        "packaged_quantity": float(line.packaged_quantity or 0),
        "shipped_quantity": float(line.shipped_quantity or 0),
        "delivered_quantity": float(line.delivered_quantity or 0),
        "accepted_quantity": float(line.accepted_quantity or 0),
        "damaged_quantity": float(line.damaged_quantity or 0),
        "missing_quantity": float(line.missing_quantity or 0),
    }


def serialize_project(project: ProductionProject, include_lines: bool = True) -> dict:
    project_lines = list(project.lines or [])
    payload = {
        "id": project.id, "project_code": project.project_code, "project_name": project.project_name,
        "customer_id": project.customer_id, "customer_name_snapshot": project.customer_name_snapshot,
        "destination_region": project.destination_region or "", "destination_city": project.destination_city or "",
        "site_name": project.site_name or "", "full_address": project.full_address or "",
        "contact_person": project.contact_person or "", "contact_phone": project.contact_phone or "",
        "planned_start_date": project.planned_start_date, "required_delivery_date": project.required_delivery_date,
        "priority": project.priority, "notes": project.notes or "", "status": project.status,
        "version": project.version, "release_revision": project.release_revision,
        "created_by": project.created_by, "created_at": project.created_at, "updated_at": project.updated_at,
        "released_at": project.released_at, "completed_at": project.completed_at, "cancelled_at": project.cancelled_at,
        "line_count": len(project_lines),
        "total_ordered_quantity": round(sum(float(line.quantity or 0) for line in project_lines), 4),
        "total_produced_quantity": round(sum(float(line.produced_quantity or 0) for line in project_lines), 4),
        "total_packaged_quantity": round(sum(float(line.packaged_quantity or 0) for line in project_lines), 4),
        "total_delivered_quantity": round(sum(float(line.delivered_quantity or 0) for line in project_lines), 4),
        "total_accepted_quantity": round(sum(float(line.accepted_quantity or 0) for line in project_lines), 4),
    }
    if include_lines:
        payload["lines"] = [serialize_line(line) for line in sorted(project_lines, key=lambda item: item.id)]
    return payload


def create_project(db: Session, data, username: str) -> ProductionProject:
    project = ProductionProject(
        project_code=data.project_code.strip(), project_name=data.project_name.strip(),
        customer_id=data.customer_id, customer_name_snapshot=data.customer_name_snapshot.strip(),
        destination_region=data.destination_region.strip(), destination_city=data.destination_city.strip(),
        site_name=data.site_name.strip(), full_address=data.full_address.strip(),
        contact_person=data.contact_person.strip(), contact_phone=data.contact_phone.strip(),
        planned_start_date=data.planned_start_date, required_delivery_date=data.required_delivery_date,
        priority=_priority(data.priority), notes=data.notes.strip(), created_by=username,
    )
    db.add(project)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ProjectError("project_code_exists", "Project code already exists", 409) from exc
    log_action(db, username, "create", "production_project", project.id, project.project_code)
    return project


def update_project(db: Session, project: ProductionProject, data, username: str) -> None:
    _editable(project); _version(project, data.expected_version)
    for field in ("project_name", "customer_id", "customer_name_snapshot", "destination_region", "destination_city", "site_name", "full_address", "contact_person", "contact_phone", "planned_start_date", "required_delivery_date", "notes"):
        value = getattr(data, field)
        if value is not None:
            setattr(project, field, value.strip() if isinstance(value, str) else value)
    if data.priority is not None:
        project.priority = _priority(data.priority)
    if data.status is not None and data.status != project.status:
        _transition(project, data.status)
    project.version += 1; project.updated_at = datetime.utcnow()
    log_action(db, username, "update", "production_project", project.id, f"version={project.version}")


def add_line(db: Session, project: ProductionProject, data, username: str) -> ProductionProjectLine:
    _editable(project)
    product = db.query(MesProductTemplate).filter(MesProductTemplate.id == data.product_id, MesProductTemplate.deleted_at.is_(None), MesProductTemplate.is_active.is_(True)).first()
    if not product:
        raise ProjectError("product_not_found", "Product not found", 404)
    existing = db.query(ProductionProjectLine).filter_by(project_id=project.id, product_id=data.product_id).first()
    if existing:
        raise ProjectError("duplicate_product_line", "Product already exists in this project", 409, {"line_id": existing.id, "current_quantity": float(existing.quantity), "proposed_quantity": float(existing.quantity) + data.quantity})
    line = ProductionProjectLine(project_id=project.id, product_id=data.product_id, quantity=data.quantity, line_reference=data.line_reference.strip(), priority=_priority(data.priority), required_date_override=data.required_date_override, notes=data.notes.strip())
    db.add(line); db.flush(); project.version += 1
    log_action(db, username, "line_add", "production_project", project.id, f"line={line.id}")
    return line


def preview_requirements(db: Session, project: ProductionProject) -> dict:
    if not project.lines:
        raise ProjectError("project_has_no_lines", "Project has no product lines")
    evidence, totals = [], {}
    for line in sorted(project.lines, key=lambda item: item.id):
        template = db.query(MesProductTemplate).options(joinedload(MesProductTemplate.bom_lines).joinedload(MesBomLine.part)).filter(MesProductTemplate.id == line.product_id).first()
        bom = active_bom_lines(template) if template else []
        if not bom:
            raise ProjectError("missing_product_bom", "A project product has no BOM", 409, {"product_id": line.product_id})
        for source in sorted(bom, key=lambda item: item.id):
            qty = float(source.required_quantity or 0)
            if qty <= 0 or not source.part:
                raise ProjectError("invalid_bom_quantity", "BOM contains an invalid detail or quantity", 409, {"bom_line_id": source.id})
            gross = qty * float(line.quantity)
            row = {"project_line_id": line.id, "product_id": line.product_id, "product_code": template.code, "product_name": template.name, "source_bom_line_id": source.id, "detail_id": source.part_id, "detail_code": source.part.part_number, "detail_name": source.part.name, "unit": source.unit or source.part.unit or "dona", "source_quantity": qty, "product_quantity": float(line.quantity), "gross_quantity": gross, "bom_revision": str(getattr(template, "updated_at", "") or "")}
            evidence.append(row)
            total = totals.setdefault(source.part_id, {"detail_id": source.part_id, "detail_code": source.part.part_number, "detail_name": source.part.name, "unit": row["unit"], "gross_required_quantity": 0.0})
            total["gross_required_quantity"] += gross
    requirements = []
    for detail_id in sorted(totals):
        row = totals[detail_id]
        available = sum(
            max(0.0, float(stock.quantity or 0) - float(stock.reserved_quantity or 0))
            for stock in db.query(WarehouseStock).filter(WarehouseStock.detail_id == detail_id).all()
        )
        gross = float(row["gross_required_quantity"])
        covered = min(gross, available)
        required = max(0.0, gross - covered)
        requirements.append({
            **row,
            "stock_available_quantity": available,
            "stock_covered_quantity": covered,
            "stock_reserved_quantity": covered,
            "production_required_quantity": required,
            "status": "stock_covered" if required <= 0 else ("partially_covered" if covered > 0 else "production_required"),
        })
    canonical = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return {"evidence": evidence, "requirements": requirements, "checksum": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


def release_project(db: Session, project_id: int, expected_version: int, key: str, username: str) -> tuple[ProductionProject, ProjectReleaseSnapshot, bool]:
    existing = db.query(ProjectReleaseSnapshot).filter_by(idempotency_key=key).first()
    if existing:
        if existing.project_id != project_id:
            raise ProjectError("idempotency_key_conflict", "Idempotency key belongs to another project", 409)
        return load_project(db, project_id), existing, True
    project = load_project(db, project_id, lock=True)
    if not project: raise ProjectError("project_not_found", "Project not found", 404)
    _version(project, expected_version)
    if project.status != "planned":
        code = "project_not_planned" if project.status == "draft" else "project_already_released"
        raise ProjectError(code, "Project must be planned before release" if project.status == "draft" else "Project has already been released", 409)
    preview = preview_requirements(db, project)
    revision = project.release_revision + 1
    release = ProjectReleaseSnapshot(project_id=project.id, revision=revision, source_project_version=project.version, idempotency_key=key, checksum=preview["checksum"], released_by=username)
    db.add(release); db.flush()
    evidence_by_line_source = {}
    for row in preview["evidence"]:
        snap = ProjectLineBomSnapshot(release_id=release.id, metadata_json={"source": "mes_bom_lines"}, **row)
        db.add(snap); db.flush(); evidence_by_line_source[(row["project_line_id"], row["source_bom_line_id"])] = snap
    requirements = {}
    for row in preview["requirements"]:
        req = ProjectDetailRequirement(
            release_id=release.id,
            detail_id=row["detail_id"],
            detail_code=row["detail_code"],
            detail_name=row["detail_name"],
            unit=row["unit"],
            gross_required_quantity=row["gross_required_quantity"],
            stock_reserved_quantity=0,
            production_required_quantity=row["gross_required_quantity"],
        )
        db.add(req); db.flush(); requirements[row["detail_id"]] = req
    for detail_id in sorted(requirements):
        req = requirements[detail_id]; remaining = float(req.gross_required_quantity)
        stocks = db.query(WarehouseStock).with_for_update().filter(WarehouseStock.detail_id == detail_id, WarehouseStock.quantity > WarehouseStock.reserved_quantity).order_by(WarehouseStock.created_at, WarehouseStock.id).all()
        for stock in stocks:
            take = min(remaining, float(stock.quantity - stock.reserved_quantity))
            if take <= 0: continue
            change_stock(db, stock.id, take, "RESERVE", username, None, f"Project {project.project_code} release {revision}")
            db.flush()
            tx = db.query(WarehouseTransaction).filter_by(stock_id=stock.id, operation="RESERVE", operator=username).order_by(WarehouseTransaction.id.desc()).first()
            db.add(ProjectStockAllocation(project_id=project.id, release_id=release.id, requirement_id=req.id, stock_id=stock.id, reserve_transaction_id=tx.id, reserved_quantity=take))
            req.stock_reserved_quantity += take; remaining -= take
            if remaining <= 0: break
        req.production_required_quantity = remaining
        req.status = "stock_covered" if remaining <= 0 else ("partially_covered" if req.stock_reserved_quantity > 0 else "production_required")
    jobs = []
    for line in sorted(project.lines, key=lambda item: item.id):
        job = MesProductionJob(job_number=f"PRJ-{project.id}-{revision}-{line.id}", customer_name=project.customer_name_snapshot, order_reference=project.project_code, template_id=line.product_id, quantity=line.quantity, priority=line.priority or project.priority, due_date=line.required_date_override or project.required_delivery_date, status="draft", created_by=username, project_id=project.id, project_line_id=line.id, project_release_snapshot_id=release.id)
        db.add(job); db.flush(); release_job_snapshot(db, job, reserve_reusable_stock=False); jobs.append(job)
        db.expire(job, ["bom_lines"])
        for job_line in job.bom_lines:
            snap = evidence_by_line_source[(line.id, job_line.source_bom_line_id)]
            job_line.project_line_bom_snapshot_id = snap.id
        line.status = "released"; line.bom_revision = str(revision)
    for detail_id, req in requirements.items():
        available = float(req.stock_reserved_quantity); relevant = sorted((s for s in evidence_by_line_source.values() if s.detail_id == detail_id), key=lambda s: (s.project_line_id, s.id))
        for snap in relevant:
            covered = min(available, float(snap.gross_quantity)); available -= covered
            job = next(j for j in jobs if j.project_line_id == snap.project_line_id)
            line = next(b for b in job.bom_lines if b.project_line_bom_snapshot_id == snap.id)
            line.stock_reserved_quantity = covered; line.production_required_quantity = float(snap.gross_quantity) - covered
    project.status = "released"; project.release_revision = revision; project.released_at = datetime.utcnow(); project.version += 1; project.updated_at = datetime.utcnow()
    log_action(db, username, "release", "production_project", project.id, json.dumps({"revision": revision, "checksum": release.checksum, "jobs": len(jobs)}))
    db.flush()
    return project, release, False


def cancel_project(db: Session, project: ProductionProject, expected_version: int, username: str, reason: str = "") -> None:
    _version(project, expected_version)
    if "cancelled" not in PRODUCTION_PROJECT_TRANSITIONS.get(project.status, set()):
        raise ProjectError("project_cannot_cancel", "Project cannot be cancelled in its current state", 409)
    allocations = db.query(ProjectStockAllocation).with_for_update().filter(ProjectStockAllocation.project_id == project.id).order_by(ProjectStockAllocation.stock_id, ProjectStockAllocation.id).all()
    total_released = 0.0
    for allocation in allocations:
        releasable = float(allocation.reserved_quantity - allocation.consumed_quantity - allocation.released_quantity)
        if releasable > 0:
            change_stock(db, allocation.stock_id, releasable, "RELEASE", username, None, f"Project {project.project_code} cancelled")
            allocation.released_quantity += releasable; allocation.status = "released" if allocation.consumed_quantity <= 0 else "partially_consumed"
            allocation.requirement.released_quantity += releasable
            total_released += releasable
    for job in db.query(MesProductionJob).filter(MesProductionJob.project_id == project.id).all():
        if job.status not in {"completed", "cancelled"}: job.status = "cancelled"
    project.status = "cancelled"; project.cancelled_at = datetime.utcnow(); project.version += 1
    log_action(db, username, "cancel", "production_project", project.id, json.dumps({"reason": reason, "released_quantity": total_released}))
