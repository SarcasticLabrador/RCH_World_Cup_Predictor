"""Scoring engine.

Applies the agreed rules (see backend/scoring_config.py):

Match predictions (group + R32..SF): exact score 5, correct result 2 — NOT
additive. The Final match is exact-score only (15). A per-stage multiplier is
available for future tweaking (currently all 1.0).

Special predictions (each worth its configured points): champion / runner-up
are derived from the Final result; the two team-stat categories are computed
from match data; the four player awards come from admin-entered actuals. Any
category can be overridden by a row in special_results.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import (
    Match,
    Prediction,
    SpecialPrediction,
    SpecialResult,
    Team,
    Tournament,
)
from backend.enums import MatchStatus, SpecialCategory, Stage
from backend.scoring_config import (
    POINTS_CORRECT_RESULT,
    POINTS_EXACT_SCORE,
    POINTS_FINAL_EXACT_SCORE,
    SPECIAL_POINTS,
    STAGE_MULTIPLIER,
)


def _sign(diff: int) -> int:
    return (diff > 0) - (diff < 0)


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


# --- Match scoring --------------------------------------------------------

def score_match_prediction(
    stage: Stage,
    pred_home: int,
    pred_away: int,
    act_home: int,
    act_away: int,
) -> int:
    """Points for a single match prediction against the actual scoreline."""
    exact = pred_home == act_home and pred_away == act_away

    if stage == Stage.FINAL:
        return POINTS_FINAL_EXACT_SCORE if exact else 0

    if exact:
        base = POINTS_EXACT_SCORE
    elif _sign(pred_home - pred_away) == _sign(act_home - act_away):
        base = POINTS_CORRECT_RESULT
    else:
        base = 0
    return int(round(base * STAGE_MULTIPLIER.get(stage, 1.0)))


def score_all_matches(db: Session, tournament: Tournament) -> int:
    """(Re)score every prediction. Finished matches get points; others reset to None."""
    matches = {
        m.id: m
        for m in db.scalars(
            select(Match).where(Match.tournament_id == tournament.id)
        ).all()
    }
    predictions = db.scalars(
        select(Prediction).join(Match).where(Match.tournament_id == tournament.id)
    ).all()

    scored = 0
    for p in predictions:
        m = matches.get(p.match_id)
        if (
            m is not None
            and m.status == MatchStatus.FINISHED
            and m.home_score is not None
            and m.away_score is not None
        ):
            p.points_awarded = score_match_prediction(
                m.stage,
                p.predicted_home_score,
                p.predicted_away_score,
                m.home_score,
                m.away_score,
            )
            scored += 1
        else:
            p.points_awarded = None  # not played yet (or result was undone)
    db.flush()
    return scored


# --- Team stats (for the two team-stat specials) --------------------------

def compute_team_stats(db: Session, tournament: Tournament) -> dict[str, dict]:
    """Per-team goals for/against and games played, from finished matches."""
    teams = {
        t.id: t.name
        for t in db.scalars(select(Team).where(Team.tournament_id == tournament.id)).all()
    }
    stats: dict[str, dict] = defaultdict(lambda: {"gf": 0, "ga": 0, "games": 0})

    matches = db.scalars(
        select(Match).where(
            Match.tournament_id == tournament.id,
            Match.status == MatchStatus.FINISHED,
        )
    ).all()
    for m in matches:
        if m.home_score is None or m.away_score is None:
            continue
        h, a = teams.get(m.home_team_id), teams.get(m.away_team_id)
        if h:
            stats[h]["gf"] += m.home_score
            stats[h]["ga"] += m.away_score
            stats[h]["games"] += 1
        if a:
            stats[a]["gf"] += m.away_score
            stats[a]["ga"] += m.home_score
            stats[a]["games"] += 1
    return dict(stats)


def _leaders(stats: dict[str, dict], key: str, most: bool) -> set[str]:
    """Team name(s) with the best per-game ratio for 'gf' or 'ga'."""
    ratios = {
        name: s[key] / s["games"] for name, s in stats.items() if s["games"] > 0
    }
    if not ratios:
        return set()
    target = max(ratios.values()) if most else min(ratios.values())
    return {name for name, r in ratios.items() if abs(r - target) < 1e-9}


# --- Special-prediction scoring -------------------------------------------

def _final_teams(db: Session, tournament: Tournament) -> tuple[str | None, str | None]:
    """(champion, runner_up) from the finished Final, else (None, None)."""
    final = db.scalar(
        select(Match).where(
            Match.tournament_id == tournament.id, Match.stage == Stage.FINAL
        )
    )
    if (
        final is None
        or final.status != MatchStatus.FINISHED
        or final.home_score is None
        or final.away_score is None
    ):
        return None, None
    teams = {
        t.id: t.name
        for t in db.scalars(select(Team).where(Team.tournament_id == tournament.id)).all()
    }
    home, away = teams.get(final.home_team_id), teams.get(final.away_team_id)
    if final.home_score >= final.away_score:
        return home, away
    return away, home


def acceptable_actuals(
    db: Session, tournament: Tournament, category: SpecialCategory
) -> set[str]:
    """Normalised set of correct answers for a category, or empty if unknown.

    A stored special_results row overrides any derived value.
    """
    stored = db.scalar(
        select(SpecialResult).where(
            SpecialResult.tournament_id == tournament.id,
            SpecialResult.category == category,
        )
    )
    if stored and stored.actual_value:
        return {_norm(stored.actual_value)}

    if category in (SpecialCategory.CHAMPION, SpecialCategory.RUNNER_UP):
        champ, runner = _final_teams(db, tournament)
        target = champ if category == SpecialCategory.CHAMPION else runner
        return {_norm(target)} if target else set()

    if category in (
        SpecialCategory.MOST_GOALS_PER_GAME,
        SpecialCategory.FEWEST_CONCEDED_PER_GAME,
    ):
        stats = compute_team_stats(db, tournament)
        if category == SpecialCategory.MOST_GOALS_PER_GAME:
            return {_norm(n) for n in _leaders(stats, "gf", most=True)}
        return {_norm(n) for n in _leaders(stats, "ga", most=False)}

    # Player awards: only known once entered manually (handled by stored above).
    return set()


def score_special_predictions(db: Session, tournament: Tournament) -> int:
    """(Re)score special predictions. Categories with unknown actuals stay None."""
    acceptable = {cat: acceptable_actuals(db, tournament, cat) for cat in SpecialCategory}

    preds = db.scalars(select(SpecialPrediction)).all()

    scored = 0
    for p in preds:
        correct_set = acceptable.get(p.category, set())
        if not correct_set:
            p.points_awarded = None  # actual not yet known
            continue
        p.points_awarded = SPECIAL_POINTS.get(p.category, 0) if _norm(p.predicted_value) in correct_set else 0
        scored += 1
    db.flush()
    return scored


def score_tournament(db: Session, tournament: Tournament) -> dict:
    """Run both scoring passes; return a small summary."""
    matches_scored = score_all_matches(db, tournament)
    specials_scored = score_special_predictions(db, tournament)
    return {"match_predictions_scored": matches_scored, "special_predictions_scored": specials_scored}
