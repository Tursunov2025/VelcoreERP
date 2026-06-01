import logging
import os
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from services.task_overdue_reminders import run_overdue_reminders_job

logger = logging.getLogger("azmus.scheduler")

_scheduler: AsyncIOScheduler | None = None


def start_reminder_scheduler() -> None:
    global _scheduler
    if os.getenv("DISABLE_REMINDER_SCHEDULER", "").lower() in ("1", "true", "yes"):
        logger.info("reminder scheduler disabled via DISABLE_REMINDER_SCHEDULER")
        return
    if _scheduler is not None:
        return

    tz_name = os.getenv("REMINDER_TIMEZONE", "Asia/Tashkent")
    hour = int(os.getenv("REMINDER_HOUR", "9"))
    minute = int(os.getenv("REMINDER_MINUTE", "0"))

    _scheduler = AsyncIOScheduler(timezone=ZoneInfo(tz_name))
    _scheduler.add_job(
        run_overdue_reminders_job,
        CronTrigger(hour=hour, minute=minute, timezone=ZoneInfo(tz_name)),
        id="overdue_task_reminders",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    logger.info(
        "reminder scheduler started daily at %02d:%02d %s",
        hour,
        minute,
        tz_name,
    )


def stop_reminder_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("reminder scheduler stopped")
