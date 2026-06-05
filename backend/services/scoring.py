"""Scoring engine implementing the bracket simulation scoring rules.

Group stage (Prediction table):
  Correct tendency 2 pts + exact score bonus 3 pts (additive).

Knockout / bracket slots (BracketPrediction table):
  Non-final: correct advancing team 2 pts + exact score bonus 3 pts.
  Final: correct champion 25 + runner-up 10 (awarded together) + exact 15.
  Penalty score is used for the exact comparison when applicable.

Special predictions (SpecialPrediction table):
  Named exact categories: 10 pts if match.
  Numeric closest-wins: 10 pts to all tied-closest.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import (
    BracketPrediction,
    BracketSlot,
    Match,
    Prediction,
    SpecialPrediction,
    SpecialResult,
    Tournament,
)
from backend.enums import MatchStatus, SpecialCategory, Stage
from backend.scoring_config import (
    AWARD_CLOSEST_PTS,
    AWARD_EXACT_PTS,
    FINAL_CHAMPION_PTS,
    FINAL_EXACT_BONUS,
    FINAL_RUNNER_UP_PTS,
    GROUP_EXACT_BONUS,
    GROUP_TENDENCY_PTS,
    KO_EXACT_BONUS,
    KO_WINNER_PTS,
    NUMERIC_CATEGORIES,
)


def _sign(diff: int) -> int:
    return (diff > 0) - (diff < 0)


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


# --- Group stage match scoring -------------------------------------------

def score_group_prediction(
    pred_home: int, pred_away: int, act_home: int, act_away: int
) -> int:
    """2 pts for correct tendency, +3 for exact score (additive)."""
    pts = 0
    if _sign(pred_home - pred_away) == _sign(act_home - act_away):
        pts += GROUP_TENDENCY_PTS
        if pred_home == act_home and pred_away == act_away:
            pts += GROUP_EXACT_BONUS
    return pts


def score_all_group_predictions(db: Session, tournament: Tournament) -> int:
    matches = {
        m.id: m
        for m in db.scalars(
            select(Match).where(Match.tournament_id == tournament.id)
        ).all()
    }
    preds = db.scalars(
        select(Prediction).join(Match).where(Match.tournament_id == tournament.id)
    ).all()

    scored = 0
    for p in preds:
        m = matches.get(p.match_id)
        if m and m.status == MatchStatus.FINISHED and m.home_score is not None:
            p.points_awarded = score_group_prediction(
                p.predicted_home_score, p.predicted_away_score,
                m.home_score, m.away_score,
            )
            scored += 1
        else:
            p.points_awarded = None
    db.flush()
    return scored


# --- Bracket slot scoring ------------------------------------------------

def _decisive_score(slot: BracketSlot) -> tuple[int, int] | None:
    """Return the scoring scoreline a user should have predicted.

    Regular time result (no penalties): the actual score, e.g. (2, 1).
    Decided by penalties: regular time score with +1 added to the winning
    side, e.g. 1-1 AET with home winning 4-3 on penalties → (2, 1).

    This means users only enter one scoreline regardless of whether the
    match went to penalties — the convention is transparent and unambiguous.
    """
    if slot.home_score is None:
        return None
    if slot.penalty_home_score is not None:
        # Determine penalty winner and add 1 to their regular time score.
        if slot.penalty_home_score > slot.penalty_away_score:
            return (slot.home_score + 1, slot.away_score)
        else:
            return (slot.home_score, slot.away_score + 1)
    return (slot.home_score, slot.away_score)


def score_bracket_prediction(
    stage: Stage,
    pred_home: int,
    pred_away: int,
    decisive_home: int,
    decisive_away: int,
) -> int:
    """Score a single bracket slot prediction."""
    pred_winner_home = pred_home >= pred_away   # home wins (or draw → home)
    actual_winner_home = decisive_home >= decisive_away
    exact = pred_home == decisive_home and pred_away == decisive_away

    if stage == Stage.FINAL:
        if pred_winner_home == actual_winner_home:
            pts = FINAL_CHAMPION_PTS + FINAL_RUNNER_UP_PTS
            if exact:
                pts += FINAL_EXACT_BONUS
            return pts
        return 0

    # Non-final knockout
    pts = 0
    if pred_winner_home == actual_winner_home:
        pts += KO_WINNER_PTS
        if exact:
            pts += KO_EXACT_BONUS
    return pts


def score_all_bracket_predictions(db: Session, tournament: Tournament) -> int:
    slots = {
        s.id: s
        for s in db.scalars(
            select(BracketSlot).where(BracketSlot.tournament_id == tournament.id)
        ).all()
    }
    preds = db.scalars(
        select(BracketPrediction)
        .join(BracketSlot)
        .where(BracketSlot.tournament_id == tournament.id)
    ).all()

    scored = 0
    for p in preds:
        slot = slots.get(p.slot_id)
        if slot is None or slot.status != MatchStatus.FINISHED:
            p.points_awarded = None
            continue
        decisive = _decisive_score(slot)
        if decisive is None:
            p.points_awarded = None
            continue
        p.points_awarded = score_bracket_prediction(
            slot.stage,
            p.predicted_home_score, p.predicted_away_score,
            decisive[0], decisive[1],
        )
        scored += 1
    db.flush()
    return scored


# --- Special / award scoring ---------------------------------------------

def _get_stored_result(db: Session, tournament: Tournament, category: SpecialCategory) -> str | None:
    row = db.scalar(
        select(SpecialResult).where(
            SpecialResult.tournament_id == tournament.id,
            SpecialResult.category == category,
        )
    )
    return row.actual_value if row else None


def score_special_predictions(db: Session, tournament: Tournament) -> int:
    """Score all special predictions.

    Named/exact categories: exact match wins 10 pts.
    Numeric categories: closest prediction(s) win 10 pts; ties share.
    Fastest goal: exact minute wins; falls back to closest if no exact.
    """
    all_preds = db.scalars(select(SpecialPrediction)).all()
    by_category: dict[SpecialCategory, list[SpecialPrediction]] = defaultdict(list)
    for p in all_preds:
        by_category[p.category].append(p)

    scored = 0
    for category, preds in by_category.items():
        actual_raw = _get_stored_result(db, tournament, category)
        if actual_raw is None:
            for p in preds:
                p.points_awarded = None
            continue

        if category in NUMERIC_CATEGORIES:
            try:
                actual_num = float(actual_raw.strip())
            except ValueError:
                for p in preds:
                    p.points_awarded = None
                continue

            # Parse predicted values.
            parsed: list[tuple[SpecialPrediction, float]] = []
            for p in preds:
                try:
                    parsed.append((p, float(p.predicted_value.strip())))
                except ValueError:
                    p.points_awarded = None

            if not parsed:
                continue

            # Find best (minimum absolute distance).
            best_dist = min(abs(v - actual_num) for _, v in parsed)

            # Fastest goal: exact minute only; fall back to closest if no exact.
            if category == SpecialCategory.FASTEST_GOAL:
                exact_hit = any(abs(v - actual_num) < 1e-9 for _, v in parsed)
                if exact_hit:
                    best_dist = 0.0  # only exact predictions win

            for p, v in parsed:
                dist = abs(v - actual_num)
                p.points_awarded = AWARD_CLOSEST_PTS if abs(dist - best_dist) < 1e-9 else 0
                scored += 1

        else:
            # Exact match (named categories + team_most_goals).
            actual_norm = _norm(actual_raw)
            for p in preds:
                p.points_awarded = AWARD_EXACT_PTS if _norm(p.predicted_value) == actual_norm else 0
                scored += 1

    db.flush()
    return scored


# --- Team stats (used by admin /team-stats endpoint) ---------------------

def compute_team_stats(db: Session, tournament: Tournament) -> dict[str, dict]:
    """Per-team goals for/against and games played, from finished group matches."""
    from collections import defaultdict
    from sqlalchemy import select as _select
    teams = {
        t.id: t.name
        for t in db.scalars(_select(Team).where(Team.tournament_id == tournament.id)).all()
    }
    stats: dict[str, dict] = defaultdict(lambda: {"gf": 0, "ga": 0, "games": 0})
    for m in db.scalars(
        _select(Match).where(
            Match.tournament_id == tournament.id,
            Match.status == MatchStatus.FINISHED,
        )
    ).all():
        if m.home_score is None:
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


# --- Combined tournament scoring -----------------------------------------

def score_tournament(db: Session, tournament: Tournament) -> dict:
    group_scored = score_all_group_predictions(db, tournament)
    bracket_scored = score_all_bracket_predictions(db, tournament)
    specials_scored = score_special_predictions(db, tournament)
    return {
        "match_predictions_scored": group_scored + bracket_scored,
        "special_predictions_scored": specials_scored,
    }
