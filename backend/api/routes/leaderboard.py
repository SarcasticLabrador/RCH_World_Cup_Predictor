"""Leaderboard endpoint: overall, per-stage, or specials."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.db.base import get_db
from backend.db.models import User
from backend.schemas import LeaderboardOut, LeaderboardRowOut
from backend.services import leaderboard as lb_service
from backend.services import seeding

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("", response_model=LeaderboardOut)
def get_leaderboard(
    scope: str = "overall",
    _current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeaderboardOut:
    tournament = seeding.get_active_tournament(db)
    if tournament is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No tournament has been seeded yet.")
    if scope not in lb_service.VALID_SCOPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown scope '{scope}'.")

    rows = lb_service.compute(db, tournament, scope, with_previous=True)
    return LeaderboardOut(
        scope=scope,
        rows=[LeaderboardRowOut(**r) for r in rows],
    )
