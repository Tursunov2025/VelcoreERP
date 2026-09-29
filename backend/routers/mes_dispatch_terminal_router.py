from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import User
from services.mes_dispatch_terminal import (
    accept_dispatch,
    dispatch_dashboard,
    dispatch_stage_ids,
    get_dispatch_stages,
    get_job_dispatch,
    list_dispatch_queue,
    load_dispatch_job,
    load_dispatch_package,
    mark_delivered,
    mark_shipped,
    serialize_terminal_job,
    start_loading,
    update_transport_info,
)
from services.permissions import require_project_job_permission, user_has_permission
from services.production_brigades import user_has_brigade_terminal_access
from services.project_execution import ExecutionError

router = APIRouter(prefix="/mes/terminal/dispatch", tags=["mes-terminal-dispatch"])


class TransportUpdate(BaseModel):
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    transport_company: Optional[str] = None


def _require_dispatch_terminal(db: Session, user: User) -> None:
    if user_has_permission(db, user, "mes_terminal_dispatch"):
        return

    stage = (
        db.query(MesProductionStage)
        .filter(
            MesProductionStage.name == "Yuklash",
            MesProductionStage.is_active.is_(True),
        )
        .first()
    )

    if stage and user_has_brigade_terminal_access(
        db,
        user_id=user.id,
        stage_id=stage.id,
    ):
        return

    raise HTTPException(
        status_code=403,
        detail="Bu terminalga kirish uchun terminal ruxsati yoki unga biriktirilgan faol brigada kerak",
    )


def _dispatch_stages_or_503(db: Session):
    stages = get_dispatch_stages(db)
    if not stages:
        raise HTTPException(status_code=503, detail="Dispatch production stages are not configured")
    return stages


@router.get("/dashboard")
def dispatch_dashboard_endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_dispatch_terminal(db, user)
    stages = _dispatch_stages_or_503(db)
    ids = {s.id for s in stages}
    stats = dispatch_dashboard(db, ids)
    return {
        "stages": [{"id": s.id, "name": s.name, "department": s.department} for s in stages],
        **stats,
    }


@router.get("/queue")
def dispatch_queue(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_dispatch_terminal(db, user)
    stages = _dispatch_stages_or_503(db)
    ids = {s.id for s in stages}
    jobs = list_dispatch_queue(db, ids)
    return {
        "stages": [{"id": s.id, "name": s.name, "department": s.department} for s in stages],
        "jobs": jobs,
    }


@router.get("/jobs/{job_id}")
def dispatch_job_detail(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_dispatch_terminal(db, user)
    stages = _dispatch_stages_or_503(db)
    ids = {s.id for s in stages}
    job = load_dispatch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize_terminal_job(db, job, ids)


@router.post("/jobs/{job_id}/accept")
def dispatch_accept(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_dispatch_terminal(db, user)
    ids = dispatch_stage_ids(db)
    job = load_dispatch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_project_job_permission(db, user, job, "production_projects_dispatch")
    try:
        accept_dispatch(db, job, ids, user.username)
    except ExecutionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(db, load_dispatch_job(db, job_id), ids)


@router.post("/jobs/{job_id}/start")
def dispatch_start_loading(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_dispatch_terminal(db, user)
    ids = dispatch_stage_ids(db)
    job = load_dispatch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_project_job_permission(db, user, job, "production_projects_dispatch")
    try:
        start_loading(db, job, ids, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(db, load_dispatch_job(db, job_id), ids)


@router.put("/jobs/{job_id}/transport")
def dispatch_update_transport(
    job_id: int,
    data: TransportUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_dispatch_terminal(db, user)
    job = load_dispatch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_project_job_permission(db, user, job, "production_projects_dispatch")
    dispatch = get_job_dispatch(db, job_id)
    if not dispatch:
        raise HTTPException(status_code=400, detail="Accept dispatch first")
    try:
        update_transport_info(
            db,
            dispatch,
            user.username,
            vehicle_number=data.vehicle_number,
            driver_name=data.driver_name,
            driver_phone=data.driver_phone,
            transport_company=data.transport_company,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    ids = dispatch_stage_ids(db)
    return serialize_terminal_job(db, load_dispatch_job(db, job_id), ids)


@router.post("/jobs/{job_id}/packages/{package_id}/load")
def dispatch_load_package(
    job_id: int,
    package_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_dispatch_terminal(db, user)
    ids = dispatch_stage_ids(db)
    job = load_dispatch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_project_job_permission(db, user, job, "production_projects_dispatch")
    try:
        load_dispatch_package(db, job, ids, user.username, package_id=package_id)
    except ExecutionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(db, load_dispatch_job(db, job_id), ids)


@router.post("/jobs/{job_id}/ship")
def dispatch_mark_shipped(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_dispatch_terminal(db, user)
    ids = dispatch_stage_ids(db)
    job = load_dispatch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_project_job_permission(db, user, job, "production_projects_dispatch")
    try:
        mark_shipped(db, job, ids, user.username)
    except ExecutionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(db, load_dispatch_job(db, job_id), ids)


@router.post("/jobs/{job_id}/deliver")
def dispatch_mark_delivered(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_dispatch_terminal(db, user)
    ids = dispatch_stage_ids(db)
    job = load_dispatch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_project_job_permission(db, user, job, "production_projects_dispatch")
    try:
        mark_delivered(db, job, ids, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return serialize_terminal_job(db, load_dispatch_job(db, job_id), ids)
