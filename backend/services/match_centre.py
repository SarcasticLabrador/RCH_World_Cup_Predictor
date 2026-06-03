"""AI Match Centre: assemble recent/upcoming fixtures and summarise via Gemini.

The fixture context always works (no AI key needed); the AI prose is layered on
top when a Gemini key is configured. Results are cached briefly to avoid
repeated API calls when several people open the page.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import Settings, get_settings
from backend.db.models import Match, Team, Tournament
from backend.enums import MatchStatus
from backend.services import gemini

_CET = ZoneInfo("Europe/Berlin")
_STAGE_DISPLAY = {
    "group": "Group Stage", "r32": "Round of 32", "r16": "Round of 16",
    "qf": "Quarter-final", "sf": "Semi-final", "final": "Final",
}

# Tiny in-memory TTL cache: key -> (expires_at, payload)
_CACHE: dict = {}
_TTL_SECONDS = 1800


def _cet(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(_CET)
    return local.strftime(f"%a %d %b, %H:%M ({local.tzname() or 'CET'})")


def _match_brief(m: Match, teams: dict) -> dict:
    return {
        "home": teams.get(m.home_team_id, "TBD"),
        "away": teams.get(m.away_team_id, "TBD"),
        "stage": m.stage.value,
        "kickoff_utc": m.kickoff_utc.isoformat(),
        "stadium": m.stadium,
        "home_score": m.home_score,
        "away_score": m.away_score,
    }


def recent_and_upcoming(
    db: Session,
    tournament: Tournament,
    now: datetime | None = None,
    lookback_hours: int = 36,
    lookahead_hours: int = 48,
) -> dict:
    now = now or datetime.now(timezone.utc)
    teams = {
        t.id: t.name
        for t in db.scalars(select(Team).where(Team.tournament_id == tournament.id)).all()
    }
    matches = db.scalars(
        select(Match).where(Match.tournament_id == tournament.id)
    ).all()

    def aware(dt):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    recent, upcoming = [], []
    for m in matches:
        ko = aware(m.kickoff_utc)
        if m.status == MatchStatus.FINISHED and ko >= now - timedelta(hours=lookback_hours):
            recent.append(m)
        elif m.status != MatchStatus.FINISHED and now <= ko <= now + timedelta(hours=lookahead_hours):
            upcoming.append(m)

    recent.sort(key=lambda m: m.kickoff_utc, reverse=True)
    upcoming.sort(key=lambda m: m.kickoff_utc)
    return {
        "recent": [_match_brief(m, teams) for m in recent],
        "upcoming": [_match_brief(m, teams) for m in upcoming],
    }


def build_prompt(context: dict, with_news: bool) -> str:
    def line(b: dict, played: bool) -> str:
        stage = _STAGE_DISPLAY.get(b["stage"], b["stage"])
        venue = f" at {b['stadium']}" if b.get("stadium") else ""
        when = _cet(datetime.fromisoformat(b["kickoff_utc"]))
        if played:
            return f"- {b['home']} {b['home_score']}–{b['away_score']} {b['away']} ({stage}, {when})"
        return f"- {b['home']} vs {b['away']} ({stage}{venue}, {when})"

    recent = "\n".join(line(b, True) for b in context["recent"]) or "- (none)"
    upcoming = "\n".join(line(b, False) for b in context["upcoming"]) or "- (none)"

    news_clause = (
        " Where relevant, weave in any notable, recent team news (injuries, "
        "line-up changes, form) and be clear it may change."
        if with_news
        else ""
    )
    return (
        "You are writing a short, upbeat update for an office World Cup "
        "prediction game. Summarise the recent results, then preview the "
        "upcoming fixtures, mentioning kickoff times (already in CET) and "
        f"stadiums.{news_clause} Keep it under ~200 words, friendly and concise. "
        "Use plain prose with at most a few short paragraphs.\n\n"
        f"RECENT RESULTS:\n{recent}\n\nUPCOMING FIXTURES:\n{upcoming}\n"
    )


def get_match_centre(
    db: Session,
    tournament: Tournament,
    with_news: bool = False,
    refresh: bool = False,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    cache_key = (with_news,)
    now = time.time()
    if not refresh and cache_key in _CACHE:
        expires_at, payload = _CACHE[cache_key]
        if expires_at > now:
            return payload

    context = recent_and_upcoming(db, tournament)
    payload = {
        "ai_available": gemini.is_configured(settings),
        "used_search": False,
        "summary": None,
        "recent": context["recent"],
        "upcoming": context["upcoming"],
    }

    if payload["ai_available"]:
        try:
            payload["summary"] = gemini.generate_text(
                build_prompt(context, with_news), use_search=with_news, settings=settings
            )
            payload["used_search"] = with_news
        except gemini.GeminiError as exc:
            payload["summary"] = None
            payload["error"] = str(exc)

    _CACHE[cache_key] = (now + _TTL_SECONDS, payload)
    return payload
