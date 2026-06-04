"""Leaderboard with split match / award / total points.

Three views:
  match  — points from group stage + all bracket slots
  awards — points from special predictions
  total  — match + awards combined

Each view has its own independent ranking.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db.models import (
    BracketPrediction,
    BracketSlot,
    LeaderboardSnapshot,
    Match,
    Prediction,
    SpecialPrediction,
    Tournament,
    User,
)


def _display(user: User) -> str:
    return user.display_name or user.email.split("@")[0]


def _assign_ranks(rows: list[dict], key: str) -> list[dict]:
    """Sort rows by key descending and assign standard competition ranks."""
    rows.sort(key=lambda r: (-r[key], r["display_name"].lower()))
    last = None
    rank = 0
    for i, row in enumerate(rows, start=1):
        if row[key] != last:
            rank = i
            last = row[key]
        row[f"{key}_rank"] = rank
    return rows


def compute(db: Session, tournament: Tournament, with_previous: bool = False) -> list[dict]:
    """Compute the combined leaderboard with match_pts, award_pts, total_pts."""
    users = db.scalars(select(User)).all()
    match_pts: dict = {u.id: 0 for u in users}
    award_pts: dict = {u.id: 0 for u in users}

    # Group stage points (Prediction table).
    for user_id, pts in db.execute(
        select(Prediction.user_id, Prediction.points_awarded)
        .join(Match, Prediction.match_id == Match.id)
        .where(Match.tournament_id == tournament.id)
    ).all():
        if pts and user_id in match_pts:
            match_pts[user_id] += pts

    # Bracket points (BracketPrediction table).
    for user_id, pts in db.execute(
        select(BracketPrediction.user_id, BracketPrediction.points_awarded)
        .join(BracketSlot, BracketPrediction.slot_id == BracketSlot.id)
        .where(BracketSlot.tournament_id == tournament.id)
    ).all():
        if pts and user_id in match_pts:
            match_pts[user_id] += pts

    # Award points (SpecialPrediction table).
    for user_id, pts in db.execute(
        select(SpecialPrediction.user_id, SpecialPrediction.points_awarded)
    ).all():
        if pts and user_id in award_pts:
            award_pts[user_id] += pts

    rows = [
        {
            "user_id": u.id,
            "display_name": _display(u),
            "match_pts": match_pts[u.id],
            "award_pts": award_pts[u.id],
            "total_pts": match_pts[u.id] + award_pts[u.id],
        }
        for u in users
    ]

    _assign_ranks(rows, "match_pts")
    _assign_ranks(rows, "award_pts")
    _assign_ranks(rows, "total_pts")

    if with_previous:
        # Load latest overall snapshot for movement arrows.
        latest = db.scalar(
            select(func.max(LeaderboardSnapshot.snapshot_at)).where(
                LeaderboardSnapshot.stage.is_(None)
            )
        )
        prev: dict = {}
        if latest:
            for uid, rank in db.execute(
                select(LeaderboardSnapshot.user_id, LeaderboardSnapshot.rank).where(
                    LeaderboardSnapshot.stage.is_(None),
                    LeaderboardSnapshot.snapshot_at == latest,
                )
            ).all():
                prev[uid] = rank
        for r in rows:
            r["previous_rank"] = prev.get(r["user_id"])

    return rows


def snapshot(db: Session, tournament: Tournament) -> int:
    """Persist the current leaderboard as a snapshot row per user."""
    rows = compute(db, tournament)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    written = 0
    for r in rows:
        snap = LeaderboardSnapshot(
            user_id=r["user_id"],
            stage=None,
            match_points=r["match_pts"],
            award_points=r["award_pts"],
            total_points=r["total_pts"],
            rank=r["total_pts_rank"],
            snapshot_at=now,
        )
        db.add(snap)
        written += 1
    db.flush()
    return written
