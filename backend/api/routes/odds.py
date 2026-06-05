"""Odds & Elo endpoint — returns implied probabilities per group stage fixture."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.config import get_settings
from backend.db.base import get_db
from backend.db.models import Match, Team, Tournament, User
from backend.enums import Stage
from backend.services import elo as elo_svc
from backend.services import odds as odds_svc
from backend.services import seeding

router = APIRouter(prefix="/odds", tags=["odds"])


@router.get("")
def get_odds(
    _current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Return Elo and market implied probabilities for all confirmed group fixtures.

    Response shape:
      {
        "elo_available": bool,
        "market_available": bool,
        "matches": {
          "<match_id>": {
            "home": "Brazil", "away": "France",
            "elo":    {"home": 0.56, "draw": 0.22, "away": 0.22},  // or null
            "market": {"home": 0.52, "draw": 0.25, "away": 0.23},  // or null
          }
        }
      }
    """
    tournament = seeding.get_active_tournament(db)
    if tournament is None:
        return {"elo_available": False, "market_available": False, "matches": {}}

    # Load all group matches with both teams known.
    matches = db.scalars(
        select(Match).where(
            Match.tournament_id == tournament.id,
            Match.stage == Stage.GROUP,
            Match.home_team_id.is_not(None),
            Match.away_team_id.is_not(None),
        )
    ).all()

    # Resolve team names.
    team_ids = {m.home_team_id for m in matches} | {m.away_team_id for m in matches}
    teams = {
        t.id: t.name
        for t in db.scalars(select(Team).where(Team.id.in_(team_ids))).all()
    }

    # Fetch data sources (both cached — ELO from DB, odds from memory).
    elo_ratings = elo_svc.fetch_elo_ratings(db)
    market_events = odds_svc.fetch_market_odds()

    result: dict[str, dict] = {}
    any_elo = False
    any_market = False

    for m in matches:
        home = teams.get(m.home_team_id)
        away = teams.get(m.away_team_id)
        if not home or not away:
            continue

        elo_p = elo_svc.elo_probabilities(home, away, elo_ratings)
        market_p = odds_svc.market_probabilities(home, away, market_events)

        if elo_p:
            any_elo = True
        if market_p:
            any_market = True

        result[str(m.id)] = {
            "home": home,
            "away": away,
            "elo": elo_p,
            "market": market_p,
        }

    return {
        "elo_available": any_elo,
        "market_available": any_market,
        "matches": result,
    }
