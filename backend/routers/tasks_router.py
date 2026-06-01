from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from auth.deps import get_current_user, require_admin
from database import get_db
from models import Task, TaskAssignment, TaskAttachment, TaskComment, User
from services.audit import log_action
from services.notifications import notify_event, notify_operator_event
from services.telegram import format_new_task_assignment_alert, format_task_status_alert

router = APIRouter(tags=["tasks"])

VALID_PRIORITIES = {"normal", "important", "urgent"}
VALID_STATUSES = {"new", "accepted", "in_progress", "completed", "cancelled"}
OPERATOR_STATUSES = {"accepted", "in_progress", "completed", "cancelled"}


# ---------- Schemas ----------
class AttachmentIn(BaseModel):
    url: str
    filename: str = ""
    content_type: str = ""
    kind: str = "task"


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    priority: str = "normal"
    deadline: Optional[str] = None
    assignee_usernames: list[str] = []
    assign_all: bool = False
    attachments: list[AttachmentIn] = []


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    deadline: Optional[str] = None
    assignee_usernames: Optional[list[str]] = None
    assign_all: Optional[bool] = None


class StatusChange(BaseModel):
    status: str
    comment: str = ""


class CommentCreate(BaseModel):
    task_id: int
    content: str
    assignment_id: Optional[int] = None


class AttachmentCreate(BaseModel):
    task_id: int
    url: str
    filename: str = ""
    content_type: str = ""
    kind: str = "task"


# ---------- Helpers ----------
def _is_admin(user: User) -> bool:
    return user.role == "admin" or user.department == "Admin"


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _operator_usernames(db: Session) -> list[str]:
    rows = (
        db.query(User)
        .filter(User.role == "operator", User.is_active.isnot(False))
        .all()
    )
    return [u.username for u in rows]


def _completion_percentage(assignments: list[TaskAssignment]) -> int:
    if not assignments:
        return 0
    done = sum(1 for a in assignments if a.status == "completed")
    return round(done / len(assignments) * 100)


def _is_overdue(task: Task) -> bool:
    if not task.deadline:
        return False
    all_done = task.assignments and all(
        a.status in ("completed", "cancelled") for a in task.assignments
    )
    return task.deadline < datetime.utcnow() and not all_done


def _serialize_assignment(a: TaskAssignment) -> dict:
    return {
        "id": a.id,
        "task_id": a.task_id,
        "operator_username": a.operator_username,
        "status": a.status,
        "accepted_at": a.accepted_at,
        "started_at": a.started_at,
        "completed_at": a.completed_at,
        "created_at": a.created_at,
    }


def _serialize_comment(c: TaskComment) -> dict:
    return {
        "id": c.id,
        "task_id": c.task_id,
        "assignment_id": c.assignment_id,
        "username": c.username,
        "content": c.content,
        "kind": c.kind,
        "status_value": c.status_value,
        "created_at": c.created_at,
    }


def _serialize_attachment(att: TaskAttachment) -> dict:
    return {
        "id": att.id,
        "task_id": att.task_id,
        "uploaded_by": att.uploaded_by,
        "url": att.url,
        "filename": att.filename,
        "content_type": att.content_type,
        "kind": att.kind,
        "created_at": att.created_at,
    }


def _serialize_task(task: Task, detailed: bool = False) -> dict:
    assignments = task.assignments or []
    data = {
        "id": task.id,
        "title": task.title,
        "description": task.description or "",
        "priority": task.priority,
        "deadline": task.deadline,
        "created_by": task.created_by,
        "assign_all": task.assign_all,
        "archived_at": task.archived_at,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "assignee_count": len(assignments),
        "accepted_count": sum(
            1 for a in assignments if a.status not in ("new", "cancelled")
        ),
        "completed_count": sum(1 for a in assignments if a.status == "completed"),
        "completion_percentage": _completion_percentage(assignments),
        "is_overdue": _is_overdue(task),
        "assignments": [_serialize_assignment(a) for a in assignments],
    }
    if detailed:
        data["comments"] = [
            _serialize_comment(c)
            for c in sorted(task.comments or [], key=lambda x: x.id)
        ]
        data["attachments"] = [
            _serialize_attachment(a) for a in (task.attachments or [])
        ]
    return data


def _load_task(db: Session, task_id: int) -> Task:
    task = (
        db.query(Task)
        .options(
            joinedload(Task.assignments),
            joinedload(Task.comments),
            joinedload(Task.attachments),
        )
        .filter(Task.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _user_assignment(task: Task, username: str) -> Optional[TaskAssignment]:
    for a in task.assignments or []:
        if a.operator_username == username:
            return a
    return None


async def _notify_assigned_operators(db: Session, task: Task, usernames: list[str]) -> None:
    if not usernames:
        return
    users = {
        u.username: u
        for u in db.query(User).filter(User.username.in_(usernames)).all()
    }
    for username in usernames:
        operator = users.get(username)
        if not operator or not operator.telegram_id:
            continue
        message = format_new_task_assignment_alert(task, username)
        await notify_operator_event(db, "new_task", message, operator.telegram_id)


# ---------- Task CRUD ----------
@router.post("/tasks")
async def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if data.priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid priority")
    if not data.title.strip():
        raise HTTPException(status_code=400, detail="Title required")

    task = Task(
        title=data.title.strip(),
        description=data.description or "",
        priority=data.priority,
        deadline=_parse_dt(data.deadline),
        created_by=admin.username,
        assign_all=bool(data.assign_all),
    )
    db.add(task)
    db.flush()

    if data.assign_all:
        usernames = _operator_usernames(db)
    else:
        usernames = list(dict.fromkeys(data.assignee_usernames or []))

    for username in usernames:
        db.add(
            TaskAssignment(
                task_id=task.id,
                operator_username=username,
                status="new",
            )
        )

    for att in data.attachments or []:
        if not att.url:
            continue
        row = TaskAttachment(
            task_id=task.id,
            uploaded_by=admin.username,
            url=att.url,
            filename=att.filename or "",
            content_type=att.content_type or "",
            kind=att.kind or "task",
        )
        db.add(row)
        db.flush()
        log_action(
            db,
            admin.username,
            "attach",
            "task_attachment",
            row.id,
            f"task={task.id} file={row.filename} url={row.url}",
        )

    log_action(db, admin.username, "create", "task", task.id, task.title)
    db.commit()
    task = _load_task(db, task.id)
    await _notify_assigned_operators(db, task, usernames)
    return _serialize_task(task, detailed=True)


@router.get("/tasks")
def list_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    scope: str = Query("auto"),  # auto | mine | all
    status: str = Query(""),
    priority: str = Query(""),
    archived: bool = Query(False),
    overdue: bool = Query(False),
    q: str = Query(""),
):
    query = db.query(Task).options(joinedload(Task.assignments))

    if archived:
        query = query.filter(Task.archived_at.isnot(None))
    else:
        query = query.filter(Task.archived_at.is_(None))

    tasks = query.order_by(Task.created_at.desc()).all()

    admin = _is_admin(user)
    show_mine = scope == "mine" or (scope == "auto" and not admin)

    result = []
    for task in tasks:
        assignment = _user_assignment(task, user.username)
        if show_mine and not assignment:
            continue
        if not admin and not assignment:
            continue

        if priority and task.priority != priority:
            continue

        serialized = _serialize_task(task)

        if status:
            if show_mine and assignment:
                if assignment.status != status:
                    continue
            else:
                if not any(a.status == status for a in task.assignments):
                    continue

        if overdue and not serialized["is_overdue"]:
            continue

        if q.strip():
            ql = q.lower()
            if ql not in task.title.lower() and ql not in (task.description or "").lower():
                continue

        if show_mine and assignment:
            serialized["my_status"] = assignment.status
            serialized["my_assignment_id"] = assignment.id

        result.append(serialized)

    return result


@router.get("/tasks/stats")
def task_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    tasks = db.query(Task).options(joinedload(Task.assignments)).all()
    active = [t for t in tasks if t.archived_at is None]
    overdue = [t for t in active if _is_overdue(t)]
    completed = [
        t
        for t in active
        if t.assignments and all(a.status == "completed" for a in t.assignments)
    ]
    return {
        "total": len(active),
        "overdue": len(overdue),
        "completed": len(completed),
        "archived": sum(1 for t in tasks if t.archived_at is not None),
    }


@router.get("/tasks/{task_id}")
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _load_task(db, task_id)
    if not _is_admin(user) and not _user_assignment(task, user.username):
        raise HTTPException(status_code=403, detail="Access denied")
    return _serialize_task(task, detailed=True)


@router.put("/tasks/{task_id}")
async def update_task(
    task_id: int,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    task = _load_task(db, task_id)

    if data.title is not None:
        task.title = data.title.strip() or task.title
    if data.description is not None:
        task.description = data.description
    if data.priority is not None:
        if data.priority not in VALID_PRIORITIES:
            raise HTTPException(status_code=400, detail="Invalid priority")
        task.priority = data.priority
    if data.deadline is not None:
        task.deadline = _parse_dt(data.deadline)

    if data.assign_all is not None:
        task.assign_all = data.assign_all

    new_usernames = None
    if data.assign_all:
        new_usernames = _operator_usernames(db)
    elif data.assignee_usernames is not None:
        new_usernames = list(dict.fromkeys(data.assignee_usernames))

    newly_assigned: list[str] = []
    if new_usernames is not None:
        existing = {a.operator_username: a for a in task.assignments}
        for username in new_usernames:
            if username not in existing:
                newly_assigned.append(username)
                db.add(
                    TaskAssignment(
                        task_id=task.id, operator_username=username, status="new"
                    )
                )
        for username, assignment in existing.items():
            if username not in new_usernames:
                db.delete(assignment)

    log_action(db, admin.username, "update", "task", task.id, task.title)
    db.commit()
    task = _load_task(db, task_id)
    await _notify_assigned_operators(db, task, newly_assigned)
    return _serialize_task(task, detailed=True)


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    task = _load_task(db, task_id)
    db.delete(task)
    log_action(db, admin.username, "delete", "task", task_id)
    db.commit()
    return {"message": "Task deleted"}


@router.post("/tasks/{task_id}/archive")
def archive_task(
    task_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    task = _load_task(db, task_id)
    task.archived_at = None if task.archived_at else datetime.utcnow()
    log_action(db, admin.username, "archive", "task", task_id)
    db.commit()
    return _serialize_task(_load_task(db, task_id), detailed=True)


# ---------- Assignments / status ----------
@router.post("/task-assignments/{assignment_id}/status")
async def change_status(
    assignment_id: int,
    data: StatusChange,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Rule: only operators can change status; boss (admin) cannot.
    if _is_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Faqat operator holatni o'zgartira oladi",
        )

    if data.status not in OPERATOR_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    assignment = (
        db.query(TaskAssignment)
        .filter(TaskAssignment.id == assignment_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.operator_username != user.username:
        raise HTTPException(status_code=403, detail="Not your task")

    now = datetime.utcnow()
    assignment.status = data.status
    if data.status == "accepted" and not assignment.accepted_at:
        assignment.accepted_at = now
    if data.status == "in_progress" and not assignment.started_at:
        assignment.started_at = now
    if data.status == "completed":
        assignment.completed_at = now

    # History log
    db.add(
        TaskComment(
            task_id=assignment.task_id,
            assignment_id=assignment.id,
            username=user.username,
            content=data.comment or "",
            kind="status",
            status_value=data.status,
        )
    )
    db.commit()
    task = _load_task(db, assignment.task_id)
    if data.status == "accepted":
        await notify_event(
            db,
            "task_accepted",
            format_task_status_alert(task, user.username, "Qabul qilindi"),
        )
    elif data.status == "completed":
        await notify_event(
            db,
            "task_completed",
            format_task_status_alert(task, user.username, "Bajarildi"),
        )
    return _serialize_task(task, detailed=True)


# ---------- Comments ----------
@router.get("/task-comments")
def list_comments(
    task_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _load_task(db, task_id)
    if not _is_admin(user) and not _user_assignment(task, user.username):
        raise HTTPException(status_code=403, detail="Access denied")
    return [
        _serialize_comment(c) for c in sorted(task.comments or [], key=lambda x: x.id)
    ]


@router.post("/task-comments")
def add_comment(
    data: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _load_task(db, data.task_id)
    if not _is_admin(user) and not _user_assignment(task, user.username):
        raise HTTPException(status_code=403, detail="Access denied")
    if not data.content.strip():
        raise HTTPException(status_code=400, detail="Empty comment")

    comment = TaskComment(
        task_id=data.task_id,
        assignment_id=data.assignment_id,
        username=user.username,
        content=data.content.strip(),
        kind="comment",
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return _serialize_comment(comment)


# ---------- Attachments ----------
@router.get("/task-attachments")
def list_attachments(
    task_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _load_task(db, task_id)
    if not _is_admin(user) and not _user_assignment(task, user.username):
        raise HTTPException(status_code=403, detail="Access denied")
    return [_serialize_attachment(a) for a in (task.attachments or [])]


@router.post("/task-attachments")
def add_attachment(
    data: AttachmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _load_task(db, data.task_id)
    is_admin = _is_admin(user)
    assignment = _user_assignment(task, user.username)
    if not is_admin and not assignment:
        raise HTTPException(status_code=403, detail="Access denied")

    # operators upload result files; admins upload task files
    kind = data.kind or ("task" if is_admin else "result")
    if not is_admin:
        kind = "result"

    attachment = TaskAttachment(
        task_id=data.task_id,
        uploaded_by=user.username,
        url=data.url,
        filename=data.filename,
        content_type=data.content_type,
        kind=kind,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return _serialize_attachment(attachment)
