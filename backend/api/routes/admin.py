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
    CreateUserIn,
    MatchResultIn,
    ResetPasswordIn,
    ScoreSummaryOut,
    SpecialResultIn,
    TeamStatOut,
    UserOut,
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
    """Manually set/override a group stage match score, then re-score everything."""
    tournament = _tournament(db)
    match = db.get(Match, body.match_id)
    if match is None or match.tournament_id != tournament.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match not found.")

    if body.finished:
        match.home_score = body.home_score
        match.away_score = body.away_score
        match.penalty_home_score = body.penalty_home_score
        match.penalty_away_score = body.penalty_away_score
        match.status = MatchStatus.FINISHED
    else:
        match.home_score = match.away_score = None
        match.penalty_home_score = match.penalty_away_score = None
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


@router.post("/seed-manual", response_model=dict)
def seed_manual(
    _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)
) -> dict:
    """Seed all 72 group stage fixtures from the hardcoded 2026 World Cup schedule."""
    from backend.services import seeding
    from backend.services.wc2026_fixtures import get_2026_fixtures, get_2026_groups

    stats = seeding.seed_world_cup(db, get_2026_fixtures(), get_2026_groups())
    db.commit()
    return stats


@router.post("/reset-password", response_model=UserOut)
def reset_password(
    body: ResetPasswordIn,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    """Reset a user's password. Admin only."""
    from backend.security import hash_password
    from backend.services.auth import get_user_by_email

    user = get_user_by_email(db, str(body.email))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No account with that email.")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/create-user", response_model=UserOut, status_code=201)
def create_user(
    body: CreateUserIn,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    """Create an account on behalf of a colleague. Bypasses the whitelist."""
    from backend.services.auth import get_user_by_email, register_user

    if get_user_by_email(db, str(body.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email already exists.")
    user = register_user(db, str(body.email), body.password, body.display_name)
    if body.is_admin:
        user.is_admin = True
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
