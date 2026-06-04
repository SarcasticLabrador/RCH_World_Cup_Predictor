"""Group standings calculation from predictions or real results.

Implements FIFA tiebreaker chain:
  1. Points (W=3, D=1, L=0)
  2. Goal difference (all group matches)
  3. Goals scored (all group matches)
  4. H2H points between tied teams
  5. H2H goal difference between tied teams
  6. H2H goals scored between tied teams
  7. Alphabetical (stable fallback instead of drawing of lots)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Match, Team, Tournament
from backend.enums import MatchStatus, Stage


class MatchResult(NamedTuple):
    home_name: str
    away_name: str
    home_score: int
    away_score: int


@dataclass
class TeamStanding:
    name: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    gf: int = 0
    ga: int = 0

    @property
    def points(self) -> int:
        return self.won * 3 + self.drawn

    @property
    def gd(self) -> int:
        return self.gf - self.ga


def _apply_result(standings: dict[str, TeamStanding], r: MatchResult) -> None:
    h, a = standings[r.home_name], standings[r.away_name]
    h.played += 1; a.played += 1
    h.gf += r.home_score; h.ga += r.away_score
    a.gf += r.away_score; a.ga += r.home_score
    if r.home_score > r.away_score:
        h.won += 1; a.lost += 1
    elif r.home_score < r.away_score:
        a.won += 1; h.lost += 1
    else:
        h.drawn += 1; a.drawn += 1


def _h2h_standings(
    tied_teams: list[str], results: list[MatchResult]
) -> dict[str, TeamStanding]:
    """Mini-standings for only the matches between the tied teams."""
    ts = {t: TeamStanding(name=t) for t in tied_teams}
    for r in results:
        if r.home_name in ts and r.away_name in ts:
            _apply_result(ts, r)
    return ts


def _sort_key(
    team: TeamStanding,
    h2h: dict[str, TeamStanding] | None = None,
) -> tuple:
    h = h2h.get(team.name, TeamStanding(name=team.name)) if h2h else TeamStanding(name=team.name)
    return (
        -team.points,
        -team.gd,
        -team.gf,
        -h.points,
        -h.gd,
        -h.gf,
        team.name.lower(),  # alphabetical tiebreak
    )


def compute_standings(
    team_names: list[str], results: list[MatchResult]
) -> list[TeamStanding]:
    """Compute and sort group standings from a list of results.

    Unplayed matches (not in results) are simply omitted — standings reflect
    only the matches for which scores are provided.
    """
    standings = {n: TeamStanding(name=n) for n in team_names}
    for r in results:
        if r.home_name in standings and r.away_name in standings:
            _apply_result(standings, r)

    rows = list(standings.values())
    rows.sort(key=lambda t: _sort_key(t))

    # Apply H2H tiebreaker for groups of tied teams.
    i = 0
    while i < len(rows):
        j = i + 1
        while j < len(rows) and rows[j].points == rows[i].points:
            j += 1
        if j - i > 1:
            tied = [r.name for r in rows[i:j]]
            h2h = _h2h_standings(tied, results)
            rows[i:j] = sorted(rows[i:j], key=lambda t: _sort_key(t, h2h))
        i = j

    return rows


def predicted_group_standings(
    group: str,
    group_matches: list[Match],
    user_preds: dict,   # {match_id: (home_score, away_score)}
) -> list[TeamStanding]:
    """Compute standings from a user's predictions for one group."""
    team_names: list[str] = []
    seen: set[str] = set()
    results: list[MatchResult] = []

    for m in group_matches:
        h_name = m.home_team.name if m.home_team else None
        a_name = m.away_team.name if m.away_team else None
        if h_name and h_name not in seen:
            team_names.append(h_name); seen.add(h_name)
        if a_name and a_name not in seen:
            team_names.append(a_name); seen.add(a_name)
        pred = user_preds.get(m.id)
        if pred and h_name and a_name:
            results.append(MatchResult(h_name, a_name, pred[0], pred[1]))

    return compute_standings(team_names, results)


def actual_group_standings(
    db: Session, tournament: Tournament, group: str
) -> list[TeamStanding]:
    """Compute standings from finished real matches for one group."""
    teams = db.scalars(
        select(Team).where(
            Team.tournament_id == tournament.id, Team.group == group
        )
    ).all()
    team_names = [t.name for t in teams]
    team_by_id = {t.id: t.name for t in teams}

    matches = db.scalars(
        select(Match).where(
            Match.tournament_id == tournament.id,
            Match.stage == Stage.GROUP,
        )
    ).all()

    results: list[MatchResult] = []
    for m in matches:
        h_name = team_by_id.get(m.home_team_id)
        a_name = team_by_id.get(m.away_team_id)
        if (
            h_name and a_name
            and m.status == MatchStatus.FINISHED
            and m.home_score is not None
        ):
            results.append(MatchResult(h_name, a_name, m.home_score, m.away_score))

    return compute_standings(team_names, results)


def rank_third_placed(
    standings_by_group: dict[str, list[TeamStanding]],
) -> list[tuple[str, str]]:
    """Rank the third-placed team from each group.

    Returns a list of (group_letter, team_name) sorted best-to-worst.
    Groups with fewer than 3 teams in the standings are skipped.
    """
    thirds: list[tuple[str, TeamStanding]] = []
    for group, rows in standings_by_group.items():
        if len(rows) >= 3:
            thirds.append((group, rows[2]))

    thirds.sort(key=lambda x: (-x[1].points, -x[1].gd, -x[1].gf, x[0].lower()))
    return [(g, t.name) for g, t in thirds]


def assign_third_to_slots(
    ranked_thirds: list[tuple[str, str]],   # (group, team_name) ordered best-first
    slot_eligibility: dict[int, list[str]], # match_number -> eligible source groups
    top_n: int = 8,
) -> dict[int, str]:
    """Assign the best N third-placed teams to the correct R32 slots.

    Uses MRV (minimum remaining values) with backtracking:
      - Always picks the most constrained remaining slot.
      - Tries eligible groups ordered by their own constraint (fewest remaining
        slots available), breaking ties by rank (best first).
      - Backtracks if a dead end is reached (no eligible group for a slot).

    Guaranteed to find a valid assignment if one exists, which it always does
    for the 2026 World Cup bracket structure across all 495 combinations of
    8 qualifying groups from 12.

    Returns {match_number: team_name}.
    """
    qualifying = ranked_thirds[:top_n]
    group_to_team = {g: name for g, name in qualifying}
    group_rank = {g: i for i, (g, _) in enumerate(qualifying)}

    def _solve(
        remaining_groups: frozenset,
        remaining_slots: frozenset,
        assigned: dict[int, str],
    ) -> dict[int, str] | None:
        if not remaining_slots:
            return assigned

        def slot_options(mn: int) -> list[str]:
            return [g for g in slot_eligibility[mn] if g in remaining_groups]

        # Most constrained slot (fewest eligible groups).
        best_slot = min(remaining_slots, key=lambda mn: len(slot_options(mn)))
        eligible = slot_options(best_slot)

        if not eligible:
            return None  # dead end — backtrack

        new_slots = remaining_slots - {best_slot}

        # Order candidates: most-constrained group first (fewest remaining slots),
        # tie-break by rank (lower index = better team).
        def group_slot_count(g: str) -> int:
            return sum(1 for mn in new_slots if g in slot_eligibility[mn])

        for group in sorted(eligible, key=lambda g: (group_slot_count(g), group_rank[g])):
            result = _solve(
                remaining_groups - {group},
                new_slots,
                {**assigned, best_slot: group_to_team[group]},
            )
            if result is not None:
                return result

        return None  # all candidates failed — backtrack

    qualifying_groups = frozenset(g for g, _ in qualifying)
    return _solve(qualifying_groups, frozenset(slot_eligibility.keys()), {}) or {}
