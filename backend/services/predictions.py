"""Prediction logic: window state, fixture listing, and submission rules."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Match, Prediction, PredictionWindow, Tournament, User
from backend.enums import Stage


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def window_state(window: PredictionWindow | None, now: datetime | None = None) -> str:
    """Return one of: 'pending', 'not_open_yet', 'open', 'closed'."""
    now = now or datetime.now(timezone.utc)
    if window is None or window.closes_at is None:
        return "pending"
    opens_at = _aware(window.opens_at)
    closes_at = _aware(window.closes_at)
    if now >= closes_at:
        return "closed"
    if opens_at is None or now < opens_at:
        return "not_open_yet"
    return "open"


def get_window(db: Session, tournament: Tournament, stage: Stage) -> PredictionWindow | None:
    return db.scalar(
        select(PredictionWindow).where(
            PredictionWindow.tournament_id == tournament.id,
            PredictionWindow.stage == stage,
        )
    )


def list_windows(db: Session, tournament: Tournament) -> list[PredictionWindow]:
    return list(
        db.scalars(
            select(PredictionWindow).where(
                PredictionWindow.tournament_id == tournament.id
            )
        ).all()
    )


def list_stage_matches(db: Session, tournament: Tournament, stage: Stage) -> list[Match]:
    return list(
        db.scalars(
            select(Match)
            .where(Match.tournament_id == tournament.id, Match.stage == stage)
            .order_by(Match.kickoff_utc)
        ).all()
    )


def user_predictions_for_matches(
    db: Session, user: User, match_ids: list
) -> dict:
    if not match_ids:
        return {}
    rows = db.scalars(
        select(Prediction).where(
            Prediction.user_id == user.id, Prediction.match_id.in_(match_ids)
        )
    ).all()
    return {p.match_id: p for p in rows}


def submit_predictions(
    db: Session,
    user: User,
    tournament: Tournament,
    stage: Stage,
    items: list[tuple],  # list of (match_id, home_score, away_score)
) -> int:
    """Upsert a user's predictions for a stage. Raises HTTPException on rules."""
    window = get_window(db, tournament, stage)
    if window_state(window) != "open":
        raise HTTPException(
            http_status.HTTP_409_CONFLICT,
            "Predictions for this stage are not currently open.",
        )

    # Only matches belonging to this stage/tournament are accepted.
    valid_ids = {
        m.id for m in list_stage_matches(db, tournament, stage)
    }
    existing = user_predictions_for_matches(db, user, [i[0] for i in items])

    saved = 0
    for match_id, home, away in items:
        if match_id not in valid_ids:
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST,
                f"Match {match_id} is not part of the {stage.value} stage.",
            )
        if home is None or away is None or home < 0 or away < 0:
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST,
                "Scores must be non-negative integers.",
            )
        pred = existing.get(match_id)
        if pred is None:
            db.add(
                Prediction(
                    user_id=user.id,
                    match_id=match_id,
                    predicted_home_score=home,
                    predicted_away_score=away,
                )
            )
        else:
            pred.predicted_home_score = home
            pred.predicted_away_score = away
        saved += 1

    db.flush()
    return saved
