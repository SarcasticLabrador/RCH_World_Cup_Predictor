"""API-Football client and parsing helpers.

Network access lives in `fetch_*`. Parsing is split into pure functions
(`map_stage`, `normalize_fixtures`, `extract_groups`) that operate on plain
dicts, so seeding can be tested with sample payloads and no network/key.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx

from backend.config import Settings, get_settings
from backend.enums import MatchStatus, Stage


@dataclass
class NormalizedMatch:
    external_id: str
    stage: Stage
    kickoff_utc: datetime
    stadium: str | None
    home_external_id: str | None
    home_name: str | None
    away_external_id: str | None
    away_name: str | None
    home_score: int | None
    away_score: int | None
    status: MatchStatus


# --- round string -> Stage ------------------------------------------------

def map_stage(round_str: str | None) -> Stage | None:
    """Map an API-Football 'round' label to our Stage. None => not predicted."""
    if not round_str:
        return None
    r = round_str.strip().lower()
    if r.startswith("group"):
        return Stage.GROUP
    if "round of 32" in r:
        return Stage.R32
    if "round of 16" in r:
        return Stage.R16
    if "quarter" in r:
        return Stage.QF
    if "semi" in r:
        return Stage.SF
    if r == "final" or r.endswith("- final") or "final" in r and "3rd" not in r and "third" not in r:
        return Stage.FINAL
    # 3rd-place play-off and anything unrecognised are not part of predictions.
    return None


_FINISHED = {"FT", "AET", "PEN"}
_LIVE = {"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT"}


def _map_status(short: str | None) -> MatchStatus:
    if short in _FINISHED:
        return MatchStatus.FINISHED
    if short in _LIVE:
        return MatchStatus.LIVE
    return MatchStatus.SCHEDULED


def _parse_dt(value: str) -> datetime:
    # API-Football returns ISO 8601 with offset, e.g. 2026-06-11T18:00:00+00:00
    return datetime.fromisoformat(value)


def normalize_fixtures(raw_response: list[dict]) -> list[NormalizedMatch]:
    """Turn API-Football '/fixtures' response items into NormalizedMatch rows.

    Skips fixtures whose round isn't part of the prediction game (e.g. the
    3rd-place play-off). Knockout fixtures with not-yet-known teams are kept,
    with team fields left None so they can be filled on a later re-seed.
    """
    out: list[NormalizedMatch] = []
    for item in raw_response:
        league = item.get("league", {})
        stage = map_stage(league.get("round"))
        if stage is None:
            continue

        fixture = item.get("fixture", {})
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        venue = (fixture.get("venue") or {})
        home = teams.get("home") or {}
        away = teams.get("away") or {}

        out.append(
            NormalizedMatch(
                external_id=str(fixture.get("id")),
                stage=stage,
                kickoff_utc=_parse_dt(fixture["date"]),
                stadium=venue.get("name"),
                home_external_id=str(home["id"]) if home.get("id") is not None else None,
                home_name=home.get("name"),
                away_external_id=str(away["id"]) if away.get("id") is not None else None,
                away_name=away.get("name"),
                home_score=goals.get("home"),
                away_score=goals.get("away"),
                status=_map_status((fixture.get("status") or {}).get("short")),
            )
        )
    return out


def extract_groups(raw_standings: list[dict]) -> dict[str, str]:
    """Map team external id -> group letter from a '/standings' response.

    The World Cup standings come back as groups ('Group A', ...), each a list
    of team rows. Returns {team_external_id: 'A'} for group assignment.
    """
    mapping: dict[str, str] = {}
    for league in raw_standings:
        for group_table in (league.get("league", {}).get("standings") or []):
            for row in group_table:
                group_name = (row.get("group") or "").strip()
                team_id = (row.get("team") or {}).get("id")
                if team_id is None or not group_name:
                    continue
                # 'Group A' -> 'A'; fall back to the raw label if unexpected.
                letter = group_name.split()[-1] if group_name.lower().startswith("group") else group_name
                mapping[str(team_id)] = letter[:2]
    return mapping


# --- network -------------------------------------------------------------

def _headers(settings: Settings) -> dict:
    return {"x-apisports-key": settings.api_football_key}


def fetch_fixtures(settings: Settings | None = None) -> list[dict]:
    settings = settings or get_settings()
    params = {
        "league": settings.api_football_wc_league_id,
        "season": settings.api_football_season,
    }
    url = f"{settings.api_football_base_url.rstrip('/')}/fixtures"
    resp = httpx.get(url, params=params, headers=_headers(settings), timeout=30.0)
    resp.raise_for_status()
    return resp.json().get("response", [])


def fetch_standings(settings: Settings | None = None) -> list[dict]:
    settings = settings or get_settings()
    params = {
        "league": settings.api_football_wc_league_id,
        "season": settings.api_football_season,
    }
    url = f"{settings.api_football_base_url.rstrip('/')}/standings"
    resp = httpx.get(url, params=params, headers=_headers(settings), timeout=30.0)
    resp.raise_for_status()
    return resp.json().get("response", [])
