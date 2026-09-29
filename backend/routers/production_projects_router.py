from typing import Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session, joinedload

from auth.deps import get_current_user
from database import get_db
from models import (
    AuditLog, MesProductionJob, ProductionProject, ProductionProjectLine,
    ProjectDetailRequirement, ProjectLineBomSnapshot, ProjectReleaseSnapshot,
    ProjectStockAllocation, User,
)
from project_schemas import (
    ProjectCancelRequest, ProjectCreate, ProjectLineCreate, ProjectLineMerge,
    ProjectLineUpdate, ProjectReleaseRequest, ProjectUpdate,
)
from services.audit import log_action
from services.permissions import user_has_permission
from services.production_projects import (
    ProjectError, add_line, cancel_project, create_project, load_project,
    preview_requirements, release_project, serialize_line, serialize_project,
    update_project,
)
from services.project_execution import project_forecast, project_progress
from services.qc_predecessor_reconciliation import reconcile_qc_predecessors
from services.stage_corrections import StageCorrectionError, correction_history, reopen_stage, return_stage

router = APIRouter(prefix="/production-projects", tags=["production-projects"])


class StageReturnRequest(BaseModel):
    job_line_id: int
    source_stage: str = Field(..., min_length=1)
    destination_stage: str = Field(..., min_length=1)
    quantity: float = Field(..., gt=0)
    reason_code: str = Field(..., min_length=1)
    comment: str = ""
    operation_key: str = Field(..., min_length=8, max_length=180)


class StageReopenRequest(BaseModel):
    stage: str = Field(..., min_length=1)
    reason_code: str = Field(..., min_length=1)
    comment: str = ""
    operation_key: str = Field(..., min_length=8, max_length=180)


class PaintReconciliationRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


def _require(db: Session, user: User, permission: str) -> None:
    if not user_has_permission(db, user, permission):
        raise HTTPException(status_code=403, detail={"code": "permission_denied", "message": f"Permission required: {permission}"})


def _error(exc: ProjectError):
    raise HTTPException(status_code=exc.status_code, detail=exc.payload()) from exc


def _correction_error(exc: StageCorrectionError):
    raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("")
def list_projects(q: str = Query(""), status: Optional[str] = Query(None), priority: Optional[str] = Query(None), destination: str = Query(""), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_view")
    query = db.query(ProductionProject)
    if q.strip():
        term = f"%{q.strip()}%"; query = query.filter(ProductionProject.project_code.ilike(term) | ProductionProject.project_name.ilike(term) | ProductionProject.customer_name_snapshot.ilike(term))
    if status: query = query.filter(ProductionProject.status == status.lower())
    if priority: query = query.filter(ProductionProject.priority == priority.lower())
    if destination.strip(): query = query.filter(ProductionProject.destination_city.ilike(f"%{destination.strip()}%"))
    total = query.count(); items = query.order_by(ProductionProject.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [serialize_project(item, False) for item in items], "total": total, "page": page, "page_size": page_size}


@router.post("", status_code=201)
def create(data: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_edit")
    try: project = create_project(db, data, user.username); db.commit()
    except ProjectError as exc: db.rollback(); _error(exc)
    return serialize_project(load_project(db, project.id))


@router.post("/jobs/{job_id}/stage-return")
def stage_return(job_id: int, data: StageReturnRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "mes_jobs_manage")
    try:
        result=return_stage(db,job_id=job_id,job_line_id=data.job_line_id,source_stage=data.source_stage,
            destination_stage=data.destination_stage,quantity=data.quantity,reason_code=data.reason_code,
            comment=data.comment,operation_key=data.operation_key,actor=user.username); db.commit(); return result
    except StageCorrectionError as exc: db.rollback(); _correction_error(exc)


@router.post("/jobs/{job_id}/stage-reopen")
def stage_reopen(job_id: int, data: StageReopenRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "mes_jobs_manage")
    try:
        result=reopen_stage(db,job_id=job_id,stage=data.stage,reason_code=data.reason_code,comment=data.comment,
            operation_key=data.operation_key,actor=user.username); db.commit(); return result
    except StageCorrectionError as exc: db.rollback(); _correction_error(exc)


@router.post("/jobs/{job_id}/paint-reconciliation")
def paint_reconciliation(job_id: int, data: PaintReconciliationRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "mes_jobs_manage")
    result=reconcile_qc_predecessors(db,job_id=job_id,dry_run=False,actor=user.username,reason=data.reason)
    if not result["applied"] and result["refused"]:
        db.rollback(); raise HTTPException(409,detail={"code":"paint_reconciliation_refused","rows":result["rows"]})
    db.commit(); return result


@router.get("/jobs/{job_id}/correction-history")
def stage_correction_history(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db,user,"production_projects_view"); return {"events":correction_history(db,job_id)}


@router.get("/{project_id}")
def detail(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_view"); project = load_project(db, project_id)
    if not project: raise HTTPException(404, detail={"code": "project_not_found", "message": "Project not found"})
    return serialize_project(project)


@router.put("/{project_id}")
def update(project_id: int, data: ProjectUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_edit"); project = load_project(db, project_id, True)
    if not project: raise HTTPException(404, detail={"code": "project_not_found"})
    try: update_project(db, project, data, user.username); db.commit()
    except ProjectError as exc: db.rollback(); _error(exc)
    return serialize_project(load_project(db, project_id))


@router.delete("/{project_id}", status_code=204)
def delete(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_edit"); project = load_project(db, project_id, True)
    if not project: raise HTTPException(404, detail={"code": "project_not_found"})
    if project.status != "draft": raise HTTPException(409, detail={"code": "project_delete_forbidden", "message": "Only draft projects may be deleted"})
    log_action(db, user.username, "delete", "production_project", project.id, project.project_code); db.delete(project); db.commit()
    return Response(status_code=204)


@router.post("/{project_id}/clone", status_code=201)
def clone(project_id: int, project_code: str = Query(..., min_length=1), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_edit"); source = load_project(db, project_id)
    if not source: raise HTTPException(404, detail={"code": "project_not_found"})
    if db.query(ProductionProject).filter_by(project_code=project_code.strip()).first(): raise HTTPException(409, detail={"code": "project_code_exists"})
    clone = ProductionProject(project_code=project_code.strip(), project_name=source.project_name, customer_id=source.customer_id, customer_name_snapshot=source.customer_name_snapshot, destination_region=source.destination_region, destination_city=source.destination_city, site_name=source.site_name, full_address=source.full_address, contact_person=source.contact_person, contact_phone=source.contact_phone, planned_start_date=source.planned_start_date, required_delivery_date=source.required_delivery_date, priority=source.priority, notes=source.notes, created_by=user.username)
    db.add(clone); db.flush()
    for line in source.lines: db.add(ProductionProjectLine(project_id=clone.id, product_id=line.product_id, quantity=line.quantity, line_reference=line.line_reference, priority=line.priority, required_date_override=line.required_date_override, notes=line.notes))
    log_action(db, user.username, "clone", "production_project", clone.id, f"source={source.id}"); db.commit()
    return serialize_project(load_project(db, clone.id))


@router.post("/{project_id}/lines", status_code=201)
def create_line(project_id: int, data: ProjectLineCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_edit"); project = load_project(db, project_id, True)
    if not project: raise HTTPException(404, detail={"code": "project_not_found"})
    try: line = add_line(db, project, data, user.username); db.commit()
    except ProjectError as exc: db.rollback(); _error(exc)
    return serialize_line(db.query(ProductionProjectLine).options(joinedload(ProductionProjectLine.product)).filter_by(id=line.id).one())


@router.put("/{project_id}/lines/{line_id}")
def update_line(project_id: int, line_id: int, data: ProjectLineUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_edit"); project = load_project(db, project_id, True)
    if not project or project.status not in {"draft", "planned"}: raise HTTPException(409, detail={"code": "project_locked"})
    line = db.query(ProductionProjectLine).with_for_update().filter_by(id=line_id, project_id=project_id).first()
    if not line: raise HTTPException(404, detail={"code": "project_line_not_found"})
    if line.version != data.expected_version: raise HTTPException(409, detail={"code": "project_line_version_conflict", "current_version": line.version})
    for field in ("quantity", "line_reference", "priority", "required_date_override", "notes"):
        value = getattr(data, field)
        if value is not None: setattr(line, field, value.strip() if isinstance(value, str) else value)
    line.version += 1; project.version += 1; log_action(db, user.username, "line_update", "production_project", project.id, f"line={line.id}"); db.commit()
    return serialize_line(db.query(ProductionProjectLine).options(joinedload(ProductionProjectLine.product)).filter_by(id=line.id).one())


@router.delete("/{project_id}/lines/{line_id}", status_code=204)
def remove_line(project_id: int, line_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_edit"); project = load_project(db, project_id, True)
    if not project or project.status not in {"draft", "planned"}: raise HTTPException(409, detail={"code": "project_locked"})
    line = db.query(ProductionProjectLine).filter_by(id=line_id, project_id=project_id).first()
    if not line: raise HTTPException(404, detail={"code": "project_line_not_found"})
    db.delete(line); project.version += 1; log_action(db, user.username, "line_remove", "production_project", project.id, f"line={line_id}"); db.commit(); return Response(status_code=204)


@router.post("/{project_id}/lines/merge")
def merge_line(project_id: int, data: ProjectLineMerge, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_edit"); project = load_project(db, project_id, True)
    if not project or project.status not in {"draft", "planned"}: raise HTTPException(409, detail={"code": "project_locked"})
    if project.version != data.expected_project_version: raise HTTPException(409, detail={"code": "project_version_conflict", "current_version": project.version})
    line = db.query(ProductionProjectLine).with_for_update().filter_by(project_id=project_id, product_id=data.product_id).first()
    if not line: raise HTTPException(404, detail={"code": "project_line_not_found"})
    line.quantity += data.additional_quantity; line.version += 1; project.version += 1; log_action(db, user.username, "line_merge", "production_project", project.id, f"line={line.id};added={data.additional_quantity}"); db.commit()
    return serialize_line(db.query(ProductionProjectLine).options(joinedload(ProductionProjectLine.product)).filter_by(id=line.id).one())


@router.get("/{project_id}/requirements/preview")
def preview(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_view"); project = load_project(db, project_id)
    if not project: raise HTTPException(404, detail={"code": "project_not_found"})
    try: return preview_requirements(db, project)
    except ProjectError as exc: _error(exc)


@router.post("/{project_id}/release")
def release(project_id: int, data: ProjectReleaseRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_release"); _require(db, user, "production_projects_stock_reserve")
    try: project, snapshot, idempotent = release_project(db, project_id, data.expected_version, data.idempotency_key.strip(), user.username); db.commit()
    except ProjectError as exc: db.rollback(); _error(exc)
    return {"project": serialize_project(load_project(db, project.id)), "release": {"id": snapshot.id, "revision": snapshot.revision, "checksum": snapshot.checksum, "idempotency_key": snapshot.idempotency_key}, "idempotent": idempotent}


@router.post("/{project_id}/cancel")
def cancel(project_id: int, data: ProjectCancelRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_cancel"); project = load_project(db, project_id, True)
    if not project: raise HTTPException(404, detail={"code": "project_not_found"})
    try: cancel_project(db, project, data.expected_version, user.username, data.reason); db.commit()
    except ProjectError as exc: db.rollback(); _error(exc)
    return serialize_project(load_project(db, project_id))


@router.get("/{project_id}/requirements")
def requirements(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_view"); release = db.query(ProjectReleaseSnapshot).filter_by(project_id=project_id).order_by(ProjectReleaseSnapshot.revision.desc()).first()
    if not release: return {"release": None, "requirements": [], "evidence": []}
    rows = db.query(ProjectDetailRequirement).filter_by(release_id=release.id).order_by(ProjectDetailRequirement.detail_code).all(); evidence = db.query(ProjectLineBomSnapshot).filter_by(release_id=release.id).order_by(ProjectLineBomSnapshot.project_line_id, ProjectLineBomSnapshot.id).all()
    return {"release": {"id": release.id, "revision": release.revision, "checksum": release.checksum}, "requirements": [{"id": r.id, "detail_id": r.detail_id, "detail_code": r.detail_code, "detail_name": r.detail_name, "unit": r.unit, "gross_required_quantity": r.gross_required_quantity, "stock_reserved_quantity": r.stock_reserved_quantity, "production_required_quantity": r.production_required_quantity, "consumed_quantity": r.consumed_quantity, "released_quantity": r.released_quantity, "status": r.status} for r in rows], "evidence": [{"id": e.id, "project_line_id": e.project_line_id, "product_id": e.product_id, "source_bom_line_id": e.source_bom_line_id, "detail_id": e.detail_id, "source_quantity": e.source_quantity, "product_quantity": e.product_quantity, "gross_quantity": e.gross_quantity} for e in evidence]}


@router.get("/{project_id}/progress")
def progress(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_view"); project = load_project(db, project_id)
    if not project: raise HTTPException(404, detail={"code": "project_not_found"})
    return project_progress(db, project)


@router.get("/{project_id}/forecast")
def forecast(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require(db, user, "production_projects_forecast"); project = load_project(db, project_id)
    if not project: raise HTTPException(404, detail={"code": "project_not_found"})
    return project_forecast(db, project)
