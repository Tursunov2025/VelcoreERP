from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from models import (
    MesTerminalBrigade,
    MesTerminalBrigadeAssignment,
    MesTerminalBrigadeMember,
    ProjectProductionOperation,
    ProjectProductionOperationParticipant,
    User,
    UserIdentityProfile,
)


def _profile_snapshot(db: Session, user: User) -> dict:
    profile = (
        db.query(UserIdentityProfile)
        .filter(UserIdentityProfile.user_id == user.id)
        .first()
    )
    return {
        "full_name": (profile.full_name if profile else "") or user.username,
        "employee_id": (profile.employee_id if profile else "") or "",
        "position": (profile.position if profile else "") or user.department or "",
    }


def brigade_assigned_to_stage(
    db: Session,
    *,
    brigade_id: int,
    stage_id: int,
) -> MesTerminalBrigade | None:
    return (
        db.query(MesTerminalBrigade)
        .join(
            MesTerminalBrigadeAssignment,
            MesTerminalBrigadeAssignment.brigade_id == MesTerminalBrigade.id,
        )
        .filter(
            MesTerminalBrigade.id == brigade_id,
            MesTerminalBrigadeAssignment.stage_id == stage_id,
            MesTerminalBrigadeAssignment.is_active.is_(True),
            MesTerminalBrigade.is_active.is_(True),
        )
        .first()
    )


def user_has_brigade_terminal_access(
    db: Session,
    *,
    user_id: int,
    stage_id: int,
) -> bool:
    """Return True when user belongs to an active brigade assigned to a terminal."""
    brigade = (
        db.query(MesTerminalBrigade.id)
        .join(
            MesTerminalBrigadeAssignment,
            MesTerminalBrigadeAssignment.brigade_id == MesTerminalBrigade.id,
        )
        .outerjoin(
            MesTerminalBrigadeMember,
            MesTerminalBrigadeMember.brigade_id == MesTerminalBrigade.id,
        )
        .filter(
            MesTerminalBrigadeAssignment.stage_id == stage_id,
            MesTerminalBrigadeAssignment.is_active.is_(True),
            MesTerminalBrigade.is_active.is_(True),
        )
        .filter(
            MesTerminalBrigade.brigadier_user_id == user_id
        )
        .first()
    )
    return brigade is not None


def resolve_brigade_for_brigadier(
    db: Session,
    *,
    stage_id: int,
    user_id: int,
) -> MesTerminalBrigade:
    brigades = (
        db.query(MesTerminalBrigade)
        .join(
            MesTerminalBrigadeAssignment,
            MesTerminalBrigadeAssignment.brigade_id == MesTerminalBrigade.id,
        )
        .filter(
            MesTerminalBrigadeAssignment.stage_id == stage_id,
            MesTerminalBrigadeAssignment.is_active.is_(True),
            MesTerminalBrigade.brigadier_user_id == user_id,
            MesTerminalBrigade.is_active.is_(True),
        )
        .all()
    )

    if not brigades:
        raise ValueError(
            "Siz ushbu terminal uchun brigadir sifatida biriktirilmagansiz"
        )

    if len(brigades) > 1:
        raise ValueError(
            "Sizga ushbu terminalda bir nechta faol brigada biriktirilgan. "
            "Admin sozlamadan faqat keraklisini qoldirsin."
        )

    return brigades[0]


def validate_worker_ids(
    db: Session,
    *,
    brigade: MesTerminalBrigade,
    worker_user_ids: list[int],
) -> list[User]:
    ids = list(dict.fromkeys(int(value) for value in worker_user_ids))

    if not ids:
        raise ValueError("Kamida bitta ishchi tanlanishi kerak")

    members = (
        db.query(User)
        .join(
            MesTerminalBrigadeMember,
            MesTerminalBrigadeMember.user_id == User.id,
        )
        .filter(
            MesTerminalBrigadeMember.brigade_id == brigade.id,
            MesTerminalBrigadeMember.user_id.in_(ids),
            MesTerminalBrigadeMember.is_active.is_(True),
            User.is_active.is_(True),
        )
        .all()
    )

    members_by_id = {user.id: user for user in members}
    missing = [user_id for user_id in ids if user_id not in members_by_id]

    if missing:
        raise ValueError(
            f"Tanlangan ishchilar ushbu brigadaga tegishli emas: {missing}"
        )

    return [members_by_id[user_id] for user_id in ids]


def attach_participants_to_operation(
    db: Session,
    *,
    operation: ProjectProductionOperation,
    brigade: MesTerminalBrigade,
    brigadier: User,
    workers: list[User],
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> None:
    operation.brigade_id = brigade.id

    existing = {
        (row.user_id, row.participation_role): row
        for row in (
            db.query(ProjectProductionOperationParticipant)
            .filter(
                ProjectProductionOperationParticipant.operation_id == operation.id,
            )
            .all()
        )
    }

    def ensure_participant(user: User, role: str) -> None:
        key = (user.id, role)
        row = existing.get(key)

        if row is None:
            snapshot = _profile_snapshot(db, user)
            row = ProjectProductionOperationParticipant(
                operation_id=operation.id,
                user_id=user.id,
                participation_role=role,
                full_name_snapshot=snapshot["full_name"],
                employee_id_snapshot=snapshot["employee_id"],
                position_snapshot=snapshot["position"],
                started_at=started_at,
                completed_at=completed_at,
            )
            db.add(row)
            existing[key] = row
            return

        if started_at and row.started_at is None:
            row.started_at = started_at
        if completed_at and row.completed_at is None:
            row.completed_at = completed_at

    ensure_participant(brigadier, "brigadier")

    for worker in workers:
        ensure_participant(worker, "worker")
