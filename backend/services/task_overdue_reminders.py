import logging
import os
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from database import SessionLocal
from models import Task, User
from services.notifications import notify_operator_event
from services.telegram import format_overdue_task_reminder

logger = logging.getLogger("azmus.reminders")

_DONE_STATUSES = frozenset({"completed", "cancelled"})


def is_task_overdue(task: Task) -> bool:
    if not task.deadline or task.archived_at:
        return False
    assignments = task.assignments or []
    if not assignments:
        return False
    all_done = all(a.status in _DONE_STATUSES for a in assignments)
    return task.deadline < datetime.utcnow() and not all_done


def _pending_assignments(task: Task):
    return [a for a in (task.assignments or []) if a.status not in _DONE_STATUSES]


async def send_overdue_task_reminders(db: Session | None = None) -> dict:
    """Send Telegram reminders for overdue tasks to assigned operators."""
    own_session = db is None
    if own_session:
        db = SessionLocal()

    sent = 0
    skipped = 0
    tasks_checked = 0

    try:
        now = datetime.utcnow()
        tasks = (
            db.query(Task)
            .options(joinedload(Task.assignments))
            .filter(
                Task.archived_at.is_(None),
                Task.deadline.isnot(None),
                Task.deadline < now,
            )
            .all()
        )

        usernames: set[str] = set()
        for task in tasks:
            if not is_task_overdue(task):
                continue
            tasks_checked += 1
            for assignment in _pending_assignments(task):
                usernames.add(assignment.operator_username)

        users = {
            u.username: u
            for u in db.query(User)
            .filter(User.username.in_(list(usernames) or [""]))
            .all()
        }

        for task in tasks:
            if not is_task_overdue(task):
                continue
            message = format_overdue_task_reminder(task)
            for assignment in _pending_assignments(task):
                operator = users.get(assignment.operator_username)
                if not operator or not operator.telegram_id:
                    skipped += 1
                    continue
                ok = await notify_operator_event(
                    db,
                    "task_overdue",
                    message,
                    operator.telegram_id,
                )
                if ok:
                    sent += 1
                else:
                    skipped += 1

        logger.info(
            "overdue reminders: tasks=%s sent=%s skipped=%s",
            tasks_checked,
            sent,
            skipped,
        )
        return {
            "tasks_checked": tasks_checked,
            "sent": sent,
            "skipped": skipped,
        }
    finally:
        if own_session:
            db.close()


async def run_overdue_reminders_job() -> None:
    try:
        await send_overdue_task_reminders()
    except Exception:
        logger.exception("overdue reminder job failed")
