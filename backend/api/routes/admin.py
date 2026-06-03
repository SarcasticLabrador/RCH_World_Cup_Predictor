"""Admin endpoints: manual result override, award entry, results refresh, rescore."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import get_current_admin
from backend.db.base import get_db
from backend.db.models import Match, SpecialResult, Tournament, User
from backend.enums import MatchStatus, SpecialCategory
from backend.schemas import (
    MatchResultIn,
    ScoreSummaryOut,
    SpecialResultIn,
    TeamStatOut,
)
from backend.services import scoring, seeding

router = APIRouter(prefix="/admin", tags=["admin"])


def _tournament(db: Session) -> Tournament:
    t = seeding.get_active_tournament(db)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No tournament seeded yet.")
    return t


@router.post("/match-result", response_model=ScoreSummaryOut)
def set_match_result(
    body: MatchResultIn,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ScoreSummaryOut:
    """Manually set/override a match score, then re-score everything."""
    tournament = _tournament(db)
    match = db.get(Match, body.match_id)
    if match is None or match.tournament_id != tournament.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match not found.")

    if body.finished:
        match.home_score = body.home_score
        match.away_score = body.away_score
        match.status = MatchStatus.FINISHED
    else:
        match.home_score = None
        match.away_score = None
        match.status = MatchStatus.SCHEDULED

    summary = scoring.score_tournament(db, tournament)
    db.commit()
    return ScoreSummaryOut(**summary)


@router.post("/special-result", response_model=ScoreSummaryOut)
def set_special_result(
    body: SpecialResultIn,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ScoreSummaryOut:
    """Set the actual winner for a special category (e.g. Golden Boot), then re-score."""
    tournament = _tournament(db)
    try:
        category = SpecialCategory(body.category)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown category '{body.category}'.")

    row = db.scalar(
        select(SpecialResult).where(
            SpecialResult.tournament_id == tournament.id,
            SpecialResult.category == category,
        )
    )
    if row is None:
        row = SpecialResult(tournament_id=tournament.id, category=category, actual_value=body.actual_value.strip())
        db.add(row)
    else:
        row.actual_value = body.actual_value.strip()
        row.updated_at = datetime.now(timezone.utc)

    summary = scoring.score_tournament(db, tournament)
    db.commit()
    return ScoreSummaryOut(**summary)


@router.post("/refresh-results", response_model=dict)
def refresh_results(
    _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)
) -> dict:
    """Pull the latest fixtures/scores from API-Football and re-score."""
    from backend.services import results

    out = results.refresh_and_score(db)
    db.commit()
    return out


@router.post("/rescore", response_model=ScoreSummaryOut)
def rescore(
    _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)
) -> ScoreSummaryOut:
    """Re-run scoring without fetching (useful after a manual change)."""
    tournament = _tournament(db)
    summary = scoring.score_tournament(db, tournament)
    db.commit()
    return ScoreSummaryOut(**summary)


@router.get("/team-stats", response_model=list[TeamStatOut])
def team_stats(
    _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)
) -> list[TeamStatOut]:
    tournament = _tournament(db)
    stats = scoring.compute_team_stats(db, tournament)
    out = []
    for name, s in stats.items():
        games = s["games"] or 1
        out.append(
            TeamStatOut(
                team=name,
                goals_for=s["gf"],
                goals_against=s["ga"],
                games=s["games"],
                goals_for_per_game=round(s["gf"] / games, 3),
                goals_against_per_game=round(s["ga"] / games, 3),
            )
        )
    out.sort(key=lambda x: x.goals_for_per_game, reverse=True)
    return out


@router.post("/run-maintenance", response_model=dict)
def run_maintenance(
    _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)
) -> dict:
    """Manually run refresh -> score -> open windows -> reminders."""
    from backend.services import tasks

    out = tasks.run_maintenance(db)
    db.commit()
    return out


@router.post("/snapshot", response_model=dict)
def snapshot(
    _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)
) -> dict:
    """Manually take a leaderboard snapshot now."""
    from backend.services import tasks

    tournament = _tournament(db)
    written = tasks.snapshot_leaderboard(db, tournament)
    db.commit()
    return {"snapshot_rows": written}
