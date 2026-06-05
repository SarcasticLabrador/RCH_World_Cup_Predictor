"""On-the-fly bracket derivation for each user.

Given a user's group stage Prediction records and BracketPrediction records,
computes which teams that user expects to be in each knockout slot.

Returns a dict: {match_number: BracketState} where BracketState has
  home_team, away_team (str | None — None means upstream not yet predicted)

Never persisted — recalculated on every request.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.db.models import BracketPrediction, BracketSlot, Match, Team, Tournament, User
from backend.enums import Stage
from backend.services import standings as st_svc
from backend.services.wc2026_bracket_slots import SLOTS_BY_NUMBER, SlotDef

GROUPS = list("ABCDEFGHIJKL")


@dataclass
class BracketState:
    home_team: str | None  # None = upstream not yet fully predicted
    away_team: str | None
    home_team_id: str | None = None
    away_team_id: str | None = None


def _slot_eligibility() -> dict[int, list[str]]:
    """Build {match_number: [eligible groups]} for Best-3rd slots."""
    result = {}
    for mn, slot in SLOTS_BY_NUMBER.items():
        if slot.away_eligible_groups:
            result[mn] = slot.away_eligible_groups
    return result


def _group_matches_by_group(
    db: Session, tournament: Tournament
) -> dict[str, list[Match]]:
    """Load all group stage matches indexed by group letter."""
    all_matches = db.scalars(
        select(Match)
        .where(
            Match.tournament_id == tournament.id,
            Match.stage == Stage.GROUP,
        )
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
        )
    ).all()
    # Eagerly load team relationships.
    by_group: dict[str, list[Match]] = {g: [] for g in GROUPS}
    for m in all_matches:
        grp = m.home_team.group if m.home_team else (m.away_team.group if m.away_team else None)
        if grp and grp in by_group:
            by_group[grp].append(m)
    return by_group


def _user_group_preds(db: Session, user: User, tournament: Tournament) -> dict:
    """Load all group stage predictions for a user as {match_id: (h, a)}."""
    from backend.db.models import Prediction
    preds = db.scalars(
        select(Prediction)
        .join(Match, Prediction.match_id == Match.id)
        .where(
            Match.tournament_id == tournament.id,
            Match.stage == Stage.GROUP,
            Prediction.user_id == user.id,
        )
    ).all()
    return {p.match_id: (p.predicted_home_score, p.predicted_away_score) for p in preds}


def _user_bracket_preds(db: Session, user: User, tournament: Tournament) -> dict[int, tuple[int, int]]:
    """Load user's bracket predictions as {match_number: (h_score, a_score)}."""
    slots = db.scalars(
        select(BracketSlot).where(BracketSlot.tournament_id == tournament.id)
    ).all()
    slot_id_to_num = {s.id: s.match_number for s in slots}

    preds = db.scalars(
        select(BracketPrediction)
        .join(BracketSlot, BracketPrediction.slot_id == BracketSlot.id)
        .where(
            BracketSlot.tournament_id == tournament.id,
            BracketPrediction.user_id == user.id,
        )
    ).all()
    return {
        slot_id_to_num[p.slot_id]: (p.predicted_home_score, p.predicted_away_score)
        for p in preds
        if p.slot_id in slot_id_to_num
    }


def _winner_from_score(home_team: str | None, away_team: str | None, h: int, a: int) -> str | None:
    """Return the predicted winner, or None if teams unknown or draw."""
    if home_team is None or away_team is None:
        return None
    if h > a:
        return home_team
    if a > h:
        return away_team
    # Draws shouldn't happen in knockout but treat home as advancing if equal.
    return home_team


def derive_bracket(
    db: Session, user: User, tournament: Tournament
) -> dict[int, BracketState]:
    """Compute the full bracket for a user from their predictions.

    Returns a dict keyed by FIFA match number (73-104).
    Teams that cannot yet be determined (upstream not predicted) are None.
    """
    # --- Step 1: derive predicted group standings ---
    matches_by_group = _group_matches_by_group(db, tournament)
    group_preds = _user_group_preds(db, user, tournament)

    standings_by_group: dict[str, list] = {}
    for grp in GROUPS:
        rows = st_svc.predicted_group_standings(grp, matches_by_group[grp], group_preds)
        standings_by_group[grp] = rows

    # Helper: team name at position in group (0=winner, 1=runner-up, 2=third)
    def group_team(grp: str, pos: int) -> str | None:
        rows = standings_by_group.get(grp, [])
        if len(rows) > pos and rows[pos].played > 0:
            return rows[pos].name
        return None  # not enough predictions to determine

    def group_complete(grp: str) -> bool:
        """True only when all 6 group matches have predictions."""
        matches = matches_by_group.get(grp, [])
        return len(matches) == 6 and all(m.id in group_preds for m in matches)

    # --- Step 2: assign Best 3rd teams to R32 slots ---
    # Only run third-place assignment when every group is fully predicted.
    # This prevents alphabetically-seeded ghost teams appearing in Best-3rd
    # slots when predictions are absent or incomplete.
    all_groups_complete = all(group_complete(g) for g in GROUPS)
    eligibility = _slot_eligibility()
    if all_groups_complete:
        ranked_thirds = st_svc.rank_third_placed(standings_by_group)
        third_assignments = st_svc.assign_third_to_slots(ranked_thirds, eligibility)
    else:
        third_assignments = {}  # Best-3rd slots stay TBD until all groups predicted

    # --- Step 3: build R32 bracket ---
    bracket: dict[int, BracketState] = {}

    # Hardcoded R32 home/away derivation from group positions.
    # Keys match SlotDef.home_descriptor / away_descriptor semantics.
    def resolve_r32_team(descriptor: str, eligible_groups: list[str], match_num: int, is_home: bool) -> str | None:
        if descriptor.startswith("Winner Group "):
            return group_team(descriptor[-1], 0)
        if descriptor.startswith("Runner-up Group "):
            return group_team(descriptor[-1], 1)
        if descriptor.startswith("Best 3rd"):
            return third_assignments.get(match_num) if not is_home else None
        return None

    for mn, slot in SLOTS_BY_NUMBER.items():
        if slot.stage != Stage.R32:
            continue
        home = resolve_r32_team(slot.home_descriptor, slot.home_eligible_groups, mn, True)
        away = resolve_r32_team(slot.away_descriptor, slot.away_eligible_groups, mn, False)
        bracket[mn] = BracketState(home_team=home, away_team=away)

    # --- Step 4: propagate R16 through Final using user's bracket predictions ---
    user_bp = _user_bracket_preds(db, user, tournament)

    ko_stages = [Stage.R16, Stage.QF, Stage.SF, Stage.FINAL]
    for stage in ko_stages:
        stage_slots = [s for s in SLOTS_BY_NUMBER.values() if s.stage == stage]
        for slot in stage_slots:
            h_team, a_team = None, None

            if slot.home_from_match:
                parent = bracket.get(slot.home_from_match)
                pred = user_bp.get(slot.home_from_match)
                if parent and pred:
                    h_team = _winner_from_score(parent.home_team, parent.away_team, pred[0], pred[1])
                elif parent:
                    h_team = None  # parent known but no prediction yet

            if slot.away_from_match:
                parent = bracket.get(slot.away_from_match)
                pred = user_bp.get(slot.away_from_match)
                if parent and pred:
                    a_team = _winner_from_score(parent.home_team, parent.away_team, pred[0], pred[1])
                elif parent:
                    a_team = None

            bracket[slot.match_number] = BracketState(home_team=h_team, away_team=a_team)

    return bracket
