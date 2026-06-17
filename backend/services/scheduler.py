import asyncio
import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from services.auto_backup import run_daily_backup
from services.gps_alerts import run_gps_alerts_sync
from services.task_overdue_reminders import run_overdue_reminders_job

logger = logging.getLogger("azmus.scheduler")

_scheduler: BackgroundScheduler | None = None


def _resolve_timezone(name: str):
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        logger.warning("timezone %s unavailable, falling back to UTC", name)
        try:
            from zoneinfo import ZoneInfo

            return ZoneInfo("UTC")
        except Exception:
            logger.warning("UTC timezone unavailable; scheduler will use APScheduler default")
            return None


def _run_overdue_reminders_sync() -> None:
    """Run async reminder job from APScheduler's background thread."""
    try:
        asyncio.run(run_overdue_reminders_job())
    except Exception:
        logger.exception("overdue reminder job failed")


def _run_daily_backup_sync() -> None:
    try:
        run_daily_backup()
    except Exception:
        logger.exception("daily backup job failed")


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
    backup_hour = int(os.getenv("BACKUP_HOUR", "2"))
    backup_minute = int(os.getenv("BACKUP_MINUTE", "0"))
    tz = _resolve_timezone(tz_name)

    trigger_kwargs = {"hour": hour, "minute": minute}
    backup_trigger = {"hour": backup_hour, "minute": backup_minute}
    if tz is not None:
        trigger_kwargs["timezone"] = tz
        backup_trigger["timezone"] = tz

    _scheduler = BackgroundScheduler(timezone=tz)
    _scheduler.add_job(
        _run_overdue_reminders_sync,
        CronTrigger(**trigger_kwargs),
        id="overdue_task_reminders",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    if os.getenv("AUTO_BACKUP_ENABLED", "true").lower() in ("1", "true", "yes"):
        _scheduler.add_job(
            _run_daily_backup_sync,
            CronTrigger(**backup_trigger),
            id="daily_database_backup",
            replace_existing=True,
            misfire_grace_time=7200,
        )
    if os.getenv("DISABLE_GPS_ALERTS", "").lower() not in ("1", "true", "yes"):
        _scheduler.add_job(
            run_gps_alerts_sync,
            IntervalTrigger(minutes=1),
            id="gps_fleet_alerts",
            replace_existing=True,
            misfire_grace_time=120,
        )
    _scheduler.start()
    logger.info(
        "reminder scheduler started daily at %02d:%02d %s; backup at %02d:%02d",
        hour,
        minute,
        tz_name if tz is not None else "server-local",
        backup_hour,
        backup_minute,
    )


def stop_reminder_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("reminder scheduler stopped")
