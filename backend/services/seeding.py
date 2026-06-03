"""Seed the database from normalized fixtures.

Idempotent: matches and teams are keyed by their API-Football external id, so
re-running (e.g. once group results fill in knockout teams) updates rather
than duplicates. Also (re)computes per-stage prediction windows.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.models import Match, PredictionWindow, Team, Tournament
from backend.enums import Stage, TournamentStatus
from backend.services.football_api import NormalizedMatch


def get_or_create_tournament(db: Session, name: str | None = None) -> Tournament:
    name = name or get_settings().tournament_name
    t = db.scalar(select(Tournament).where(Tournament.name == name))
    if t is None:
        t = Tournament(name=name, status=TournamentStatus.UPCOMING)
        db.add(t)
        db.flush()
    return t


def get_active_tournament(db: Session) -> Tournament | None:
    """The tournament we run the game for (single-tournament app: the first)."""
    name = get_settings().tournament_name
    t = db.scalar(select(Tournament).where(Tournament.name == name))
    return t or db.scalar(select(Tournament))


def _upsert_team(
    db: Session,
    tournament: Tournament,
    external_id: str | None,
    name: str | None,
    group: str | None,
) -> Team | None:
    if not external_id or not name:
        return None  # knockout placeholder with unknown team
    team = db.scalar(
        select(Team).where(
            Team.tournament_id == tournament.id, Team.external_id == external_id
        )
    )
    if team is None:
        team = Team(
            tournament_id=tournament.id,
            external_id=external_id,
            name=name,
            group=group,
        )
        db.add(team)
        db.flush()
    else:
        team.name = name
        if group:
            team.group = group
    return team


def seed_world_cup(
    db: Session,
    fixtures: list[NormalizedMatch],
    groups: dict[str, str] | None = None,
    tournament_name: str | None = None,
) -> dict:
    """Upsert tournament/teams/matches/windows. Returns simple stats."""
    groups = groups or {}
    tournament = get_or_create_tournament(db, tournament_name)

    teams_seen: set[str] = set()
    matches_created = 0
    matches_updated = 0

    for nm in fixtures:
        home = _upsert_team(
            db, tournament, nm.home_external_id, nm.home_name,
            groups.get(nm.home_external_id or ""),
        )
        away = _upsert_team(
            db, tournament, nm.away_external_id, nm.away_name,
            groups.get(nm.away_external_id or ""),
        )
        for t in (home, away):
            if t is not None:
                teams_seen.add(str(t.external_id))

        match = db.scalar(
            select(Match).where(
                Match.tournament_id == tournament.id, Match.external_id == nm.external_id
            )
        )
        if match is None:
            db.add(
                Match(
                    tournament_id=tournament.id,
                    external_id=nm.external_id,
                    stage=nm.stage,
                    kickoff_utc=nm.kickoff_utc,
                    stadium=nm.stadium,
                    home_team_id=home.id if home else None,
                    away_team_id=away.id if away else None,
                    home_score=nm.home_score,
                    away_score=nm.away_score,
                    status=nm.status,
                )
            )
            matches_created += 1
        else:
            match.stage = nm.stage
            match.kickoff_utc = nm.kickoff_utc
            match.stadium = nm.stadium
            match.home_team_id = home.id if home else match.home_team_id
            match.away_team_id = away.id if away else match.away_team_id
            match.home_score = nm.home_score
            match.away_score = nm.away_score
            match.status = nm.status
            matches_updated += 1

    db.flush()
    windows = recompute_windows(db, tournament)

    return {
        "tournament": tournament.name,
        "teams": len(teams_seen),
        "matches_created": matches_created,
        "matches_updated": matches_updated,
        "windows": windows,
    }


def recompute_windows(db: Session, tournament: Tournament) -> int:
    """Create/refresh a PredictionWindow per stage.

    closes_at = kickoff of the earliest match in that stage. The group window
    opens immediately (predictions available as soon as fixtures are seeded);
    knockout windows keep opens_at = None until the previous round concludes
    (set by the Phase 6 scheduler).
    """
    matches = db.scalars(
        select(Match).where(Match.tournament_id == tournament.id)
    ).all()

    earliest: dict[Stage, datetime] = {}
    for m in matches:
        ko = m.kickoff_utc
        if ko.tzinfo is None:
            ko = ko.replace(tzinfo=timezone.utc)
        if m.stage not in earliest or ko < earliest[m.stage]:
            earliest[m.stage] = ko

    count = 0
    for stage, closes_at in earliest.items():
        window = db.scalar(
            select(PredictionWindow).where(
                PredictionWindow.tournament_id == tournament.id,
                PredictionWindow.stage == stage,
            )
        )
        if window is None:
            window = PredictionWindow(tournament_id=tournament.id, stage=stage)
            db.add(window)
        window.closes_at = closes_at
        if stage == Stage.GROUP and window.opens_at is None:
            window.opens_at = datetime.now(timezone.utc)
        count += 1

    db.flush()
    return count
