"""Seed the database from normalized fixtures and bracket slots.

Idempotent: keyed on external_id (matches) and match_number (bracket slots).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.models import BracketSlot, Match, PredictionWindow, Team, Tournament
from backend.enums import MatchStatus, Stage, TournamentStatus
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
    name = get_settings().tournament_name
    t = db.scalar(select(Tournament).where(Tournament.name == name))
    return t or db.scalar(select(Tournament))


def _upsert_team(db, tournament, external_id, name, group) -> Team | None:
    if not external_id or not name:
        return None
    team = db.scalar(
        select(Team).where(
            Team.tournament_id == tournament.id, Team.external_id == external_id
        )
    )
    if team is None:
        team = Team(tournament_id=tournament.id, external_id=external_id,
                    name=name, group=group)
        db.add(team)
        db.flush()
    else:
        team.name = name
        if group:
            team.group = group
    return team


def seed_world_cup(db, fixtures, groups=None, tournament_name=None) -> dict:
    groups = groups or {}
    tournament = get_or_create_tournament(db, tournament_name)

    teams_seen: set[str] = set()
    matches_created = matches_updated = 0

    for nm in fixtures:
        home = _upsert_team(db, tournament, nm.home_external_id, nm.home_name,
                             groups.get(nm.home_external_id or ""))
        away = _upsert_team(db, tournament, nm.away_external_id, nm.away_name,
                             groups.get(nm.away_external_id or ""))
        for t in (home, away):
            if t is not None:
                teams_seen.add(str(t.external_id))

        match = db.scalar(
            select(Match).where(
                Match.tournament_id == tournament.id, Match.external_id == nm.external_id
            )
        )
        if match is None:
            db.add(Match(
                tournament_id=tournament.id, external_id=nm.external_id,
                stage=nm.stage, kickoff_utc=nm.kickoff_utc, stadium=nm.stadium,
                home_team_id=home.id if home else None,
                away_team_id=away.id if away else None,
                home_score=nm.home_score, away_score=nm.away_score, status=nm.status,
            ))
            matches_created += 1
        else:
            match.stage = nm.stage; match.kickoff_utc = nm.kickoff_utc
            match.stadium = nm.stadium
            match.home_team_id = home.id if home else match.home_team_id
            match.away_team_id = away.id if away else match.away_team_id
            match.home_score = nm.home_score; match.away_score = nm.away_score
            match.status = nm.status
            matches_updated += 1

    db.flush()
    windows = recompute_windows(db, tournament)
    slots = seed_bracket_slots(db, tournament)

    return {
        "tournament": tournament.name,
        "teams": len(teams_seen),
        "matches_created": matches_created,
        "matches_updated": matches_updated,
        "windows": windows,
        "bracket_slots": slots,
    }


def seed_bracket_slots(db: Session, tournament: Tournament) -> int:
    """Upsert all knockout bracket slots from the hardcoded definitions."""
    from backend.services.wc2026_bracket_slots import BRACKET_SLOTS

    created = 0
    for slotdef in BRACKET_SLOTS:
        existing = db.scalar(
            select(BracketSlot).where(
                BracketSlot.tournament_id == tournament.id,
                BracketSlot.match_number == slotdef.match_number,
            )
        )
        kickoff = datetime.fromisoformat(slotdef.kickoff_utc)
        if existing is None:
            db.add(BracketSlot(
                tournament_id=tournament.id,
                match_number=slotdef.match_number,
                stage=slotdef.stage,
                home_descriptor=slotdef.home_descriptor,
                away_descriptor=slotdef.away_descriptor,
                kickoff_utc=kickoff,
                venue=slotdef.venue,
                status=MatchStatus.SCHEDULED,
            ))
            created += 1
        else:
            existing.home_descriptor = slotdef.home_descriptor
            existing.away_descriptor = slotdef.away_descriptor
            existing.kickoff_utc = kickoff
            existing.venue = slotdef.venue

    db.flush()
    return created


def recompute_windows(db: Session, tournament: Tournament) -> int:
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
