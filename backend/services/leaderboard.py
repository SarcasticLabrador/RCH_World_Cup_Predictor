"""Leaderboard computation: overall, per-stage, and specials.

Points come from already-computed `points_awarded` (None counts as 0). Ties
share the same rank (standard competition ranking: 1, 2, 2, 4 ...), per the
'display as tied' decision. All registered users appear, even with 0 points.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db.models import (
    LeaderboardSnapshot,
    Match,
    Prediction,
    SpecialPrediction,
    Tournament,
    User,
)
from backend.enums import Stage

STAGE_SCOPES = {s.value for s in Stage}
VALID_SCOPES = {"overall", "specials"} | STAGE_SCOPES


def _display(user: User) -> str:
    return user.display_name or user.email.split("@")[0]


def _assign_ranks(rows: list[dict]) -> list[dict]:
    """rows must be pre-sorted by points desc. Equal points share a rank."""
    last_points = None
    rank = 0
    for i, row in enumerate(rows, start=1):
        if row["points"] != last_points:
            rank = i
            last_points = row["points"]
        row["rank"] = rank
    return rows


def latest_snapshot_ranks(db: Session, scope: str) -> dict:
    """Map user_id -> rank from the most recent snapshot for a scope.

    'specials' has no stored snapshot (no enum value), so returns empty.
    """
    if scope == "specials":
        return {}
    stage_val = None if scope == "overall" else Stage(scope)

    cond = (
        LeaderboardSnapshot.stage.is_(None)
        if stage_val is None
        else LeaderboardSnapshot.stage == stage_val
    )
    latest = db.scalar(select(func.max(LeaderboardSnapshot.snapshot_at)).where(cond))
    if latest is None:
        return {}
    rows = db.execute(
        select(LeaderboardSnapshot.user_id, LeaderboardSnapshot.rank).where(
            cond, LeaderboardSnapshot.snapshot_at == latest
        )
    ).all()
    return {uid: rank for uid, rank in rows}


def compute(
    db: Session, tournament: Tournament, scope: str, with_previous: bool = False
) -> list[dict]:
    if scope not in VALID_SCOPES:
        raise ValueError(f"Unknown scope '{scope}'")

    users = db.scalars(select(User)).all()
    points: dict = {u.id: 0 for u in users}

    include_matches = scope == "overall" or scope in STAGE_SCOPES
    include_specials = scope in ("overall", "specials")

    if include_matches:
        rows = db.execute(
            select(Prediction.user_id, Prediction.points_awarded, Match.stage)
            .join(Match, Prediction.match_id == Match.id)
            .where(Match.tournament_id == tournament.id)
        ).all()
        for user_id, pts, stage in rows:
            if pts is None or user_id not in points:
                continue
            if scope == "overall" or stage.value == scope:
                points[user_id] += pts

    if include_specials:
        srows = db.execute(
            select(SpecialPrediction.user_id, SpecialPrediction.points_awarded)
        ).all()
        for user_id, pts in srows:
            if pts and user_id in points:
                points[user_id] += pts

    result = [
        {"user_id": u.id, "display_name": _display(u), "points": points[u.id]}
        for u in users
    ]
    # Sort by points desc, then name for a stable, readable order.
    result.sort(key=lambda r: (-r["points"], r["display_name"].lower()))
    _assign_ranks(result)

    if with_previous:
        prev = latest_snapshot_ranks(db, scope)
        for r in result:
            r["previous_rank"] = prev.get(r["user_id"])
    return result
