"""In-process scheduler (APScheduler).

Runs maintenance on an interval and a daily leaderboard snapshot. Requires the
backend to be running continuously. For free hosts that sleep, disable this
(SCHEDULER_ENABLED=false) and drive the same jobs via an external cron hitting
the /tasks/* endpoints instead.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.config import get_settings
from backend.db.base import SessionLocal
from backend.services import seeding, tasks

logger = logging.getLogger("worldcup.scheduler")

_scheduler: BackgroundScheduler | None = None


def _maintenance_job() -> None:
    db = SessionLocal()
    try:
        tasks.run_maintenance(db)
    except Exception:
        logger.exception("Maintenance job crashed")
    finally:
        db.close()


def _snapshot_job() -> None:
    db = SessionLocal()
    try:
        tournament = seeding.get_active_tournament(db)
        if tournament is not None:
            tasks.snapshot_leaderboard(db, tournament)
            db.commit()
    except Exception:
        db.rollback()
        logger.exception("Snapshot job crashed")
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    settings = get_settings()
    if not settings.scheduler_enabled or _scheduler is not None:
        return

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _maintenance_job,
        IntervalTrigger(minutes=settings.results_poll_minutes),
        id="maintenance",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _snapshot_job,
        CronTrigger(hour=settings.snapshot_hour_cet, minute=0, timezone="Europe/Berlin"),
        id="daily_snapshot",
    )
    _scheduler.start()
    logger.info(
        "Scheduler started (maintenance every %s min, snapshot at %02d:00 CET).",
        settings.results_poll_minutes,
        settings.snapshot_hour_cet,
    )


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
