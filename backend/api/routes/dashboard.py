"""Single dashboard endpoint — returns everything the frontend needs on first load.

Replaces five separate round-trip calls (windows, fixtures, bracket slots,
leaderboard, odds) with one request. Each section is computed independently
so a failure in one doesn't break the others.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.db.base import get_db
from backend.db.models import User
from backend.services import seeding

log = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Aggregate endpoint: windows + group fixtures + bracket slots + leaderboard + odds.

    Each section degrades independently — if odds fail, the rest still returns.
    Response shape:
      {
        "windows":       [...],
        "group_fixtures": {...},   # StageFixturesOut shape
        "bracket_slots": {...},    # BracketSlotsOut shape
        "leaderboard":   {...},    # LeaderboardOut shape
        "odds":          {...},    # odds shape
      }
    """
    tournament = seeding.get_active_tournament(db)
    if tournament is None:
        return {
            "windows": [],
            "group_fixtures": None,
            "bracket_slots": None,
            "leaderboard": None,
            "odds": None,
        }

    result: dict = {}

    # --- Windows ---
    try:
        from backend.services import predictions as pred_svc
        from backend.schemas import WindowOut
        windows = pred_svc.list_windows(db, tournament)
        result["windows"] = [
            WindowOut(
                stage=w.stage.value,
                opens_at=w.opens_at,
                closes_at=w.closes_at,
                state=pred_svc.window_state(w),
            ).model_dump()
            for w in sorted(windows, key=lambda w: (w.closes_at or w.stage.value))
        ]
    except Exception as exc:
        log.warning("Dashboard: windows failed — %s", exc)
        result["windows"] = []

    # --- Group fixtures (incl. user's predictions) ---
    try:
        from backend.enums import Stage
        from backend.schemas import FixtureOut, StageFixturesOut
        from backend.services import predictions as pred_svc
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        from backend.db.models import Match

        matches = db.scalars(
            select(Match)
            .where(Match.tournament_id == tournament.id, Match.stage == Stage.GROUP)
            .options(selectinload(Match.home_team), selectinload(Match.away_team))
        ).all()

        window = pred_svc.get_window(db, tournament, Stage.GROUP)
        preds = pred_svc.user_predictions_for_matches(db, current, [m.id for m in matches])

        fixtures = [
            FixtureOut(
                match_id=m.id,
                stage=m.stage.value,
                home_team=m.home_team.name if m.home_team else None,
                away_team=m.away_team.name if m.away_team else None,
                kickoff_utc=m.kickoff_utc,
                stadium=m.stadium,
                home_score=m.home_score,
                away_score=m.away_score,
                penalty_home_score=m.penalty_home_score,
                penalty_away_score=m.penalty_away_score,
                predicted_home_score=preds[m.id].predicted_home_score if m.id in preds else None,
                predicted_away_score=preds[m.id].predicted_away_score if m.id in preds else None,
            ).model_dump()
            for m in matches
        ]
        result["group_fixtures"] = StageFixturesOut(
            stage=Stage.GROUP.value,
            state=pred_svc.window_state(window),
            fixtures=fixtures,
        ).model_dump()
    except Exception as exc:
        log.warning("Dashboard: group fixtures failed — %s", exc)
        result["group_fixtures"] = None

    # --- Bracket slots + derived teams ---
    try:
        from backend.db.models import BracketPrediction, BracketSlot
        from backend.schemas import BracketSlotOut, BracketSlotsOut
        from backend.services import bracket as bracket_svc
        from sqlalchemy import select, func

        existing_count = db.scalar(
            select(func.count(BracketSlot.id)).where(BracketSlot.tournament_id == tournament.id)
        )
        if not existing_count:
            from backend.services import seeding as seed_svc
            seed_svc.seed_bracket_slots(db, tournament)
            db.commit()

        slots = db.scalars(
            select(BracketSlot)
            .where(BracketSlot.tournament_id == tournament.id)
            .order_by(BracketSlot.match_number)
        ).all()

        preds_map = {
            bp.slot_id: bp
            for bp in db.scalars(
                select(BracketPrediction)
                .join(BracketSlot)
                .where(
                    BracketSlot.tournament_id == tournament.id,
                    BracketPrediction.user_id == current.id,
                )
            ).all()
        }

        derived = bracket_svc.derive_bracket(db, current, tournament)

        bracket_out = []
        for s in slots:
            bp = preds_map.get(s.id)
            d = derived.get(s.match_number)
            bracket_out.append(BracketSlotOut(
                slot_id=s.id,
                match_number=s.match_number,
                stage=s.stage.value,
                home_descriptor=s.home_descriptor,
                away_descriptor=s.away_descriptor,
                kickoff_utc=s.kickoff_utc,
                venue=s.venue,
                home_team=s.home_team.name if s.home_team else None,
                away_team=s.away_team.name if s.away_team else None,
                home_score=s.home_score,
                away_score=s.away_score,
                penalty_home_score=s.penalty_home_score,
                penalty_away_score=s.penalty_away_score,
                status=s.status.value,
                predicted_home_score=bp.predicted_home_score if bp else None,
                predicted_away_score=bp.predicted_away_score if bp else None,
                derived_home_team=d.home_team if d else None,
                derived_away_team=d.away_team if d else None,
            ).model_dump())

        result["bracket_slots"] = {"slots": bracket_out}
    except Exception as exc:
        log.warning("Dashboard: bracket slots failed — %s", exc)
        result["bracket_slots"] = None

    # --- Leaderboard ---
    try:
        from backend.schemas import LeaderboardRowOut
        from backend.services import leaderboard as lb_svc
        rows = lb_svc.compute(db, tournament, with_previous=True)
        result["leaderboard"] = {
            "rows": [LeaderboardRowOut(**r).model_dump() for r in rows]
        }
    except Exception as exc:
        log.warning("Dashboard: leaderboard failed — %s", exc)
        result["leaderboard"] = None

    # --- Odds ---
    try:
        from backend.db.models import Team
        from backend.services import elo as elo_svc
        from backend.services import odds as odds_svc
        from sqlalchemy import select

        all_matches = result.get("group_fixtures", {}) or {}
        fixtures_list = (all_matches.get("fixtures") or []) if isinstance(all_matches, dict) else []

        team_ids = set()
        match_objs_by_id = {}
        from backend.db.models import Match
        from backend.enums import Stage
        gmatches = db.scalars(
            select(Match).where(
                Match.tournament_id == tournament.id,
                Match.stage == Stage.GROUP,
                Match.home_team_id.is_not(None),
                Match.away_team_id.is_not(None),
            )
        ).all()
        for m in gmatches:
            team_ids.add(m.home_team_id)
            team_ids.add(m.away_team_id)
            match_objs_by_id[m.id] = m

        teams = {
            t.id: t.name
            for t in db.scalars(select(Team).where(Team.id.in_(team_ids))).all()
        }

        elo_ratings = elo_svc.fetch_elo_ratings(db)
        market_events = odds_svc.fetch_market_odds()

        odds_result: dict = {}
        any_elo = False
        any_market = False
        for m in gmatches:
            home = teams.get(m.home_team_id)
            away = teams.get(m.away_team_id)
            if not home or not away:
                continue
            elo_p = elo_svc.elo_probabilities(home, away, elo_ratings)
            market_p = odds_svc.market_probabilities(home, away, market_events)
            if elo_p: any_elo = True
            if market_p: any_market = True
            odds_result[str(m.id)] = {"home": home, "away": away, "elo": elo_p, "market": market_p}

        result["odds"] = {
            "elo_available": any_elo,
            "market_available": any_market,
            "matches": odds_result,
        }
    except Exception as exc:
        log.warning("Dashboard: odds failed — %s", exc)
        result["odds"] = {"elo_available": False, "market_available": False, "matches": {}}

    result["predictions_locked"] = getattr(tournament, "predictions_locked", False)
    return result
