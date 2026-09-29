from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import (
    MesProductionStage,
    MesTerminalBrigade,
    MesTerminalBrigadeAssignment,
    MesTerminalBrigadeMember,
    User,
    UserIdentityProfile,
)
from services.permissions import user_has_permission


router = APIRouter(
    prefix="/mes/brigades",
    tags=["mes-brigades"],
)


def _require_manage(db: Session, user: User) -> None:
    if user_has_permission(db, user, "mes_jobs_manage"):
        return
    raise HTTPException(
        status_code=403,
        detail="Permission required: mes_jobs_manage",
    )


def _user_payload(db: Session, user: User) -> dict:
    profile = (
        db.query(UserIdentityProfile)
        .filter(UserIdentityProfile.user_id == user.id)
        .first()
    )

    return {
        "id": user.id,
        "username": user.username,
        "full_name": (profile.full_name if profile else "") or user.username,
        "employee_id": (profile.employee_id if profile else "") or "",
        "position": (profile.position if profile else "") or "",
        "department": user.department or "",
        "role": user.role or "",
        "is_active": bool(user.is_active),
    }


def _brigade_payload(db: Session, brigade: MesTerminalBrigade) -> dict:
    brigadier = (
        db.query(User)
        .filter(User.id == brigade.brigadier_user_id)
        .first()
    )

    assignments = (
        db.query(MesTerminalBrigadeAssignment, MesProductionStage)
        .join(
            MesProductionStage,
            MesProductionStage.id == MesTerminalBrigadeAssignment.stage_id,
        )
        .filter(
            MesTerminalBrigadeAssignment.brigade_id == brigade.id,
            MesTerminalBrigadeAssignment.is_active.is_(True),
            MesProductionStage.is_active.is_(True),
        )
        .order_by(MesProductionStage.sort_order.asc(), MesProductionStage.name.asc())
        .all()
    )

    terminals = [
        {
            "id": stage.id,
            "name": stage.name,
            "department": stage.department or "",
        }
        for _, stage in assignments
    ]

    members = (
        db.query(User)
        .join(
            MesTerminalBrigadeMember,
            MesTerminalBrigadeMember.user_id == User.id,
        )
        .filter(
            MesTerminalBrigadeMember.brigade_id == brigade.id,
            MesTerminalBrigadeMember.is_active.is_(True),
            User.is_active.is_(True),
        )
        .order_by(User.username.asc())
        .all()
    )

    legacy_stage = assignments[0][1] if assignments else None

    return {
        "id": brigade.id,
        "name": brigade.name,
        "stage": (
            {
                "id": legacy_stage.id,
                "name": legacy_stage.name,
                "department": legacy_stage.department or "",
            }
            if legacy_stage
            else None
        ),
        "stage_id": legacy_stage.id if legacy_stage else brigade.stage_id,
        "stage_ids": [stage.id for _, stage in assignments],
        "terminals": terminals,
        "brigadier": _user_payload(db, brigadier) if brigadier else None,
        "members": [_user_payload(db, user) for user in members],
        "is_active": bool(brigade.is_active),
        "created_by": brigade.created_by or "",
        "updated_by": brigade.updated_by or "",
        "created_at": brigade.created_at,
        "updated_at": brigade.updated_at,
    }


@router.get("/my-access")
def my_brigade_terminal_access(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(MesProductionStage)
        .join(
            MesTerminalBrigadeAssignment,
            MesTerminalBrigadeAssignment.stage_id == MesProductionStage.id,
        )
        .join(
            MesTerminalBrigade,
            MesTerminalBrigade.id == MesTerminalBrigadeAssignment.brigade_id,
        )
        .filter(
            MesProductionStage.is_active.is_(True),
            MesTerminalBrigadeAssignment.is_active.is_(True),
            MesTerminalBrigade.is_active.is_(True),
            MesTerminalBrigade.brigadier_user_id == user.id,
        )
        .order_by(
            MesProductionStage.sort_order.asc(),
            MesProductionStage.name.asc(),
        )
        .all()
    )

    stage_ids = [stage.id for stage in rows]
    terminals = [
        {
            "id": stage.id,
            "name": stage.name,
            "department": stage.department or "",
        }
        for stage in rows
    ]

    permission_map = {
        "Lazer": "mes_terminal_lazer",
        "Svarshik": "mes_terminal_svarshik",
        "Kraska": "mes_terminal_kraska",
        "Nazorat": "mes_terminal_qc",
        "Yig‘ish": "mes_terminal_yigish",
        "Upakovka": "mes_terminal_packaging",
        "Sklad": "mes_terminal_warehouse",
        "Yuklash": "mes_terminal_dispatch",
    }

    permissions = [
        permission_map[stage.name]
        for stage in rows
        if stage.name in permission_map
    ]

    return {
        "user_id": user.id,
        "is_brigadier": bool(rows),
        "stage_ids": stage_ids,
        "terminals": terminals,
        "permissions": permissions,
    }


class BrigadePayload(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    brigadier_user_id: int = Field(..., gt=0)
    member_user_ids: list[int] = Field(default_factory=list)

    # New source of truth.
    stage_ids: list[int] = Field(default_factory=list)

    # Backward-compatible legacy field.
    stage_id: int | None = Field(default=None, gt=0)


class BrigadeStatusPayload(BaseModel):
    is_active: bool


def _validate_users(
    db: Session,
    brigadier_user_id: int,
    member_user_ids: list[int],
) -> tuple[User, list[User]]:
    ids = list(dict.fromkeys(int(value) for value in member_user_ids))
    all_ids = list(dict.fromkeys([brigadier_user_id, *ids]))

    users = (
        db.query(User)
        .filter(
            User.id.in_(all_ids),
            User.is_active.is_(True),
        )
        .all()
    )

    users_by_id = {user.id: user for user in users}
    missing = [user_id for user_id in all_ids if user_id not in users_by_id]

    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "inactive_or_missing_user",
                "user_ids": missing,
            },
        )

    brigadier = users_by_id[brigadier_user_id]
    members = [
        users_by_id[user_id]
        for user_id in ids
        if user_id in users_by_id
    ]

    return brigadier, members


def _validate_stage_ids(db: Session, data: BrigadePayload) -> list[int]:
    requested = list(dict.fromkeys(int(x) for x in data.stage_ids if int(x) > 0))

    if not requested and data.stage_id:
        requested = [int(data.stage_id)]

    if not requested:
        return []

    stages = (
        db.query(MesProductionStage)
        .filter(
            MesProductionStage.id.in_(requested),
            MesProductionStage.is_active.is_(True),
        )
        .all()
    )

    by_id = {stage.id: stage for stage in stages}
    missing = [stage_id for stage_id in requested if stage_id not in by_id]

    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "inactive_or_missing_stage",
                "stage_ids": missing,
            },
        )

    return requested


def _sync_assignments(
    db: Session,
    *,
    brigade: MesTerminalBrigade,
    stage_ids: list[int],
    username: str,
) -> None:
    now = datetime.utcnow()

    existing = (
        db.query(MesTerminalBrigadeAssignment)
        .filter(MesTerminalBrigadeAssignment.brigade_id == brigade.id)
        .all()
    )
    by_stage = {row.stage_id: row for row in existing}
    wanted = set(stage_ids)

    for row in existing:
        row.is_active = row.stage_id in wanted
        row.updated_by = username
        row.updated_at = now

    for stage_id in stage_ids:
        row = by_stage.get(stage_id)

        if row:
            row.is_active = True
            row.updated_by = username
            row.updated_at = now
        else:
            db.add(
                MesTerminalBrigadeAssignment(
                    brigade_id=brigade.id,
                    stage_id=stage_id,
                    is_active=True,
                    created_by=username,
                    updated_by=username,
                    created_at=now,
                    updated_at=now,
                )
            )

    # Keep legacy field synchronized only as compatibility metadata.
    brigade.stage_id = stage_ids[0] if stage_ids else None


@router.get("")
def list_brigades(
    stage_id: int | None = Query(None, gt=0),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)

    query = db.query(MesTerminalBrigade)

    if stage_id is not None:
        query = (
            query.join(
                MesTerminalBrigadeAssignment,
                MesTerminalBrigadeAssignment.brigade_id == MesTerminalBrigade.id,
            )
            .filter(
                MesTerminalBrigadeAssignment.stage_id == stage_id,
                MesTerminalBrigadeAssignment.is_active.is_(True),
            )
        )

    if not include_inactive:
        query = query.filter(MesTerminalBrigade.is_active.is_(True))

    rows = query.order_by(MesTerminalBrigade.name.asc()).distinct().all()

    return {
        "items": [_brigade_payload(db, row) for row in rows],
        "total": len(rows),
    }


@router.get("/users")
def list_brigade_users(
    department: str = "",
    q: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)

    query = (
        db.query(User)
        .outerjoin(
            UserIdentityProfile,
            UserIdentityProfile.user_id == User.id,
        )
        .filter(User.is_active.is_(True))
    )

    if department.strip():
        query = query.filter(User.department == department.strip())

    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            (User.username.ilike(term))
            | (UserIdentityProfile.full_name.ilike(term))
            | (UserIdentityProfile.employee_id.ilike(term))
        )

    users = query.order_by(User.username.asc()).all()

    return {
        "items": [_user_payload(db, row) for row in users],
        "total": len(users),
    }


@router.post("")
def create_brigade(
    data: BrigadePayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)

    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Brigade name is required")

    existing = (
        db.query(MesTerminalBrigade)
        .filter(MesTerminalBrigade.name == name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Brigade with this name already exists",
        )

    stage_ids = _validate_stage_ids(db, data)
    brigadier, members = _validate_users(
        db,
        data.brigadier_user_id,
        data.member_user_ids,
    )

    now = datetime.utcnow()

    brigade = MesTerminalBrigade(
        stage_id=stage_ids[0] if stage_ids else None,
        name=name,
        brigadier_user_id=brigadier.id,
        is_active=True,
        created_by=user.username,
        updated_by=user.username,
        created_at=now,
        updated_at=now,
    )
    db.add(brigade)
    db.flush()

    for member in members:
        db.add(
            MesTerminalBrigadeMember(
                brigade_id=brigade.id,
                user_id=member.id,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )

    _sync_assignments(
        db,
        brigade=brigade,
        stage_ids=stage_ids,
        username=user.username,
    )

    db.commit()
    db.refresh(brigade)

    return _brigade_payload(db, brigade)


@router.put("/{brigade_id}")
def update_brigade(
    brigade_id: int,
    data: BrigadePayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)

    brigade = (
        db.query(MesTerminalBrigade)
        .filter(MesTerminalBrigade.id == brigade_id)
        .first()
    )
    if not brigade:
        raise HTTPException(status_code=404, detail="Brigade not found")

    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Brigade name is required")

    duplicate = (
        db.query(MesTerminalBrigade)
        .filter(
            MesTerminalBrigade.name == name,
            MesTerminalBrigade.id != brigade.id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="Brigade with this name already exists",
        )

    stage_ids = _validate_stage_ids(db, data)
    brigadier, members = _validate_users(
        db,
        data.brigadier_user_id,
        data.member_user_ids,
    )

    brigade.name = name
    brigade.brigadier_user_id = brigadier.id
    brigade.updated_by = user.username
    brigade.updated_at = datetime.utcnow()

    existing_members = (
        db.query(MesTerminalBrigadeMember)
        .filter(MesTerminalBrigadeMember.brigade_id == brigade.id)
        .all()
    )
    member_by_user = {row.user_id: row for row in existing_members}
    wanted_ids = {member.id for member in members}

    now = datetime.utcnow()

    for row in existing_members:
        row.is_active = row.user_id in wanted_ids
        row.updated_at = now

    for member in members:
        row = member_by_user.get(member.id)

        if row:
            row.is_active = True
            row.updated_at = now
        else:
            db.add(
                MesTerminalBrigadeMember(
                    brigade_id=brigade.id,
                    user_id=member.id,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )

    _sync_assignments(
        db,
        brigade=brigade,
        stage_ids=stage_ids,
        username=user.username,
    )

    db.commit()
    db.refresh(brigade)

    return _brigade_payload(db, brigade)


@router.post("/{brigade_id}/status")
def set_brigade_status(
    brigade_id: int,
    data: BrigadeStatusPayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_manage(db, user)

    brigade = (
        db.query(MesTerminalBrigade)
        .filter(MesTerminalBrigade.id == brigade_id)
        .first()
    )
    if not brigade:
        raise HTTPException(status_code=404, detail="Brigade not found")

    brigade.is_active = bool(data.is_active)
    brigade.updated_by = user.username
    brigade.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(brigade)

    return _brigade_payload(db, brigade)
