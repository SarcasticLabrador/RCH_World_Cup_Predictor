"""Scheduled/triggerable jobs, written as plain functions.

These can be driven by the in-process scheduler (backend/scheduler.py), by an
admin button, or by an external cron via /tasks/*. Each function commits its
own work where appropriate and is defensive so one failure doesn't cascade.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.db.models import Tournament
from backend.enums import MatchStatus, Stage
from backend.services import leaderboard as lb
from backend.services import predictions as pred_service
from backend.services import seeding

logger = logging.getLogger("worldcup.tasks")

PREVIOUS_STAGE = {
    Stage.R32: Stage.GROUP,
    Stage.R16: Stage.R32,
    Stage.QF:  Stage.R16,
    Stage.SF:  Stage.QF,
    Stage.FINAL: Stage.SF,
}

STAGE_DISPLAY = {
    Stage.GROUP: "Group Stage",
    Stage.R32:   "Round of 32",
    Stage.R16:   "Round of 16",
    Stage.QF:    "Quarter-finals",
    Stage.SF:    "Semi-finals",
    Stage.FINAL: "Final",
}


def _stage_concluded(db: Session, tournament: Tournament, stage: Stage) -> bool:
    matches = pred_service.list_stage_matches(db, tournament, stage)
    return bool(matches) and all(m.status == MatchStatus.FINISHED for m in matches)


def open_due_windows(db: Session, tournament: Tournament) -> list[str]:
    """Open a knockout prediction window once its preceding round has fully concluded."""
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


def snapshot_leaderboard(db: Session, tournament: Tournament) -> int:
    """Persist current standings with a timestamp."""
    return lb.snapshot(db, tournament)


def run_maintenance(db: Session) -> dict:
    """Score → open due windows. Called by scheduler and admin panel."""
    tournament = seeding.get_active_tournament(db)
    if tournament is None:
        return {"skipped": "no tournament seeded"}

    out: dict = {}
    try:
        from backend.services import scoring
        out["scoring"] = scoring.score_tournament(db, tournament)
        db.commit()
    except Exception as exc:
        db.rollback()
        out["score_error"] = str(exc)
        logger.exception("Scoring failed")

    try:
        out["windows_opened"] = open_due_windows(db, tournament)
        db.commit()
    except Exception as exc:
        db.rollback()
        out["open_error"] = str(exc)
        logger.exception("Opening windows failed")

    return out
