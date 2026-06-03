"""AI Match Centre endpoint: recent/upcoming fixtures plus an optional AI summary."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.db.base import get_db
from backend.db.models import User
from backend.schemas import MatchCentreOut
from backend.services import match_centre, seeding

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/match-centre", response_model=MatchCentreOut)
def get_match_centre(
    news: bool = False,
    refresh: bool = False,
    _current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MatchCentreOut:
    """Recent results + upcoming fixtures, with an AI summary if a key is set.

    `news=true` lets the summary pull in recent team news via Google Search
    grounding. `refresh=true` bypasses the short server-side cache.
    """
    tournament = seeding.get_active_tournament(db)
    if tournament is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No tournament has been seeded yet.")
    data = match_centre.get_match_centre(db, tournament, with_news=news, refresh=refresh)
    return MatchCentreOut(**{k: data[k] for k in MatchCentreOut.model_fields})
