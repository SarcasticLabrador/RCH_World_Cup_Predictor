"""Scheduled/triggerable jobs, written as plain functions.

These can be driven by the in-process scheduler (backend/scheduler.py), by an
admin button, or by an external cron via /tasks/*. Each function commits its
own work where appropriate and is defensive so one failure doesn't cascade.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.models import LeaderboardSnapshot, Tournament, User
from backend.enums import MatchStatus, Stage
from backend.services import leaderboard as lb
from backend.services import predictions as pred_service
from backend.services import results, seeding
from backend.services.email import get_email_sender
from backend.services.email_templates import reminder_email

logger = logging.getLogger("worldcup.tasks")

# Which stage's completion unlocks the next stage's prediction window.
PREVIOUS_STAGE = {
    Stage.R32: Stage.GROUP,
    Stage.R16: Stage.R32,
    Stage.QF: Stage.R16,
    Stage.SF: Stage.QF,
    Stage.FINAL: Stage.SF,
}

STAGE_DISPLAY = {
    Stage.GROUP: "Group Stage",
    Stage.R32: "Round of 32",
    Stage.R16: "Round of 16",
    Stage.QF: "Quarter-finals",
    Stage.SF: "Semi-finals",
    Stage.FINAL: "Final",
}


def _stage_concluded(db: Session, tournament: Tournament, stage: Stage) -> bool:
    matches = pred_service.list_stage_matches(db, tournament, stage)
    return bool(matches) and all(m.status == MatchStatus.FINISHED for m in matches)


def open_due_windows(db: Session, tournament: Tournament) -> list[str]:
    """Open a knockout window once its preceding round has fully concluded."""
    now = datetime.now(timezone.utc)
    opened: list[str] = []
    for stage, prev in PREVIOUS_STAGE.items():
        window = pred_service.get_window(db, tournament, stage)
        if window is None or window.opens_at is not None:
            continue
        if _stage_concluded(db, tournament, prev):
            window.opens_at = now
            opened.append(stage.value)
    db.flush()
    return opened


def send_due_reminders(db: Session, tournament: Tournament) -> list[str]:
    """Email participants once per window, when it becomes open."""
    settings = get_settings()
    sender = get_email_sender(settings)
    users = db.scalars(select(User)).all()
    app_url = settings.app_base_url

    sent: list[str] = []
    for window in pred_service.list_windows(db, tournament):
        if window.reminder_sent or pred_service.window_state(window) != "open":
            continue
        display = STAGE_DISPLAY.get(window.stage, window.stage.value)
        subject, html, text = reminder_email(display, app_url)
        for u in users:
            try:
                sender.send(u.email, subject, html, text)
            except Exception:  # one bad address shouldn't stop the rest
                logger.exception("Reminder send failed for %s", u.email)
        window.reminder_sent = True
        sent.append(window.stage.value)
    db.flush()
    return sent


def snapshot_leaderboard(db: Session, tournament: Tournament) -> int:
    """Persist current standings (overall + per stage) with a timestamp."""
    now = datetime.now(timezone.utc)
    written = 0
    scopes = ["overall"] + [s.value for s in Stage]
    for scope in scopes:
        rows = lb.compute(db, tournament, scope)
        stage_val = None if scope == "overall" else Stage(scope)
        for r in rows:
            db.add(
                LeaderboardSnapshot(
                    user_id=r["user_id"],
                    stage=stage_val,
                    total_points=r["points"],
                    rank=r["rank"],
                    snapshot_at=now,
                )
            )
            written += 1
    db.flush()
    return written


def run_maintenance(db: Session) -> dict:
    """Refresh results -> score -> open due windows -> send reminders."""
    tournament = seeding.get_active_tournament(db)
    if tournament is None:
        return {"skipped": "no tournament seeded"}

    out: dict = {}
    try:
        out["refresh"] = results.refresh_and_score(db)
        db.commit()
    except Exception as exc:
        db.rollback()
        out["refresh_error"] = str(exc)
        logger.exception("Results refresh failed")

    try:
        out["windows_opened"] = open_due_windows(db, tournament)
        db.commit()
    except Exception as exc:
        db.rollback()
        out["open_error"] = str(exc)
        logger.exception("Opening windows failed")

    try:
        out["reminders_sent"] = send_due_reminders(db, tournament)
        db.commit()
    except Exception as exc:
        db.rollback()
        out["reminder_error"] = str(exc)
        logger.exception("Sending reminders failed")

    return out
