"""The Odds API service — market-implied probabilities per fixture.

Fetches h2h (head-to-head) odds for the FIFA World Cup from the-odds-api.com,
averages across all returned bookmakers, and converts to normalised implied
probabilities (overround removed).

Requires ODDS_API_KEY in settings. If the key is absent or the API returns no
data for the World Cup (e.g. pre-tournament), the caller receives None per
match and degrades gracefully.

Free-tier limit: 500 requests/month. We cache for 1 hour so each user page
load doesn't cost a request. A full day of activity costs at most 24 requests.
"""
from __future__ import annotations

import logging
import time
import unicodedata
from datetime import datetime, timezone

import httpx

from backend.config import get_settings

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Name normalisation                                                           #
# --------------------------------------------------------------------------- #

# The Odds API name → our database name (FIFA 2026 fixtures spelling)
_ODDS_NAME_MAP: dict[str, str] = {
    "united states":            "united states",
    "usa":                      "united states",
    "south korea":              "south korea",
    "korea republic":           "south korea",
    "ivory coast":              "côte d'ivoire",
    "cote d'ivoire":            "côte d'ivoire",
    "iran":                     "iran",
    "ir iran":                  "iran",
    "bosnia and herzegovina":   "bosnia & herzegovina",
    "cape verde islands":       "cape verde",
    # Name changes — Odds API may use old or new spelling
    "czech republic":           "czechia",
    "czechia":                  "czechia",
    "turkey":                   "turkiye",
    "turkiye":                  "turkiye",
    "türkiye":                  "turkiye",
}


def _norm(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name.lower())
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(ascii_str.split())


def _canonical(name: str) -> str:
    n = _norm(name)
    return _ODDS_NAME_MAP.get(n, n)


# --------------------------------------------------------------------------- #
# Fetching                                                                     #
# --------------------------------------------------------------------------- #

_CACHE: dict = {"data": [], "fetched_at": 0.0}
_TTL = 3600   # 1 hour

# Sport key for FIFA World Cup on The Odds API.
# The actual key may vary; we try both common variants.
_SPORT_KEYS = ["soccer_fifa_world_cup", "soccer_world_cup"]


def fetch_market_odds(force: bool = False) -> list[dict]:
    """Return raw Odds API event list (all WC fixtures with bookmaker odds).

    Returns [] if the API key is absent, the tournament is not yet listed,
    or any network/API error occurs.
    """
    settings = get_settings()
    if not settings.odds_api_key:
        return []

    now = time.time()
    if not force and _CACHE["data"] is not None and now - _CACHE["fetched_at"] < _TTL:
        return _CACHE["data"]

    data = _fetch(settings.odds_api_key, settings.odds_api_base_url)
    _CACHE["data"] = data
    _CACHE["fetched_at"] = now
    return data


def _fetch(api_key: str, base_url: str) -> list[dict]:
    """Try each sport key until one returns data."""
    with httpx.Client(timeout=10) as client:
        for sport_key in _SPORT_KEYS:
            try:
                r = client.get(
                    f"{base_url}/sports/{sport_key}/odds/",
                    params={
                        "apiKey": api_key,
                        "regions": "eu",
                        "markets": "h2h",
                        "dateFormat": "iso",
                    },
                )
                if r.status_code == 404:
                    continue   # sport key not found, try next
                r.raise_for_status()
                data = r.json()
                if isinstance(data, list):
                    log.info("Fetched %d Odds API events (sport: %s)", len(data), sport_key)
                    return data
            except Exception as exc:
                log.warning("Odds API fetch failed for %s: %s", sport_key, exc)
    return []


# --------------------------------------------------------------------------- #
# Probability extraction                                                       #
# --------------------------------------------------------------------------- #

def _implied_probs(outcomes: list[dict]) -> dict[str, float]:
    """Convert a list of {name, price} outcomes to normalised implied probs."""
    raw = {o["name"]: 1.0 / o["price"] for o in outcomes if o.get("price", 0) > 0}
    total = sum(raw.values())
    if total == 0:
        return {}
    return {name: round(p / total, 3) for name, p in raw.items()}


def market_probabilities(
    home_team: str, away_team: str, events: list[dict]
) -> dict[str, float] | None:
    """Match a fixture to the odds data and return {home, draw, away} probs.

    Averages probabilities across all bookmakers for robustness.
    Returns None if no matching event found.
    """
    h_can = _canonical(home_team)
    a_can = _canonical(away_team)

    for event in events:
        ev_home = _canonical(event.get("home_team", ""))
        ev_away = _canonical(event.get("away_team", ""))
        if ev_home != h_can or ev_away != a_can:
            continue

        bookmaker_probs: list[dict] = []
        for bm in event.get("bookmakers", []):
            for market in bm.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                probs = _implied_probs(market.get("outcomes", []))
                if len(probs) == 3:   # must have all three outcomes
                    bookmaker_probs.append(probs)

        if not bookmaker_probs:
            return None

        # Average across bookmakers.
        home_p = sum(p.get(event["home_team"], 0) for p in bookmaker_probs) / len(bookmaker_probs)
        away_p = sum(p.get(event["away_team"], 0) for p in bookmaker_probs) / len(bookmaker_probs)
        draw_p = sum(p.get("Draw", 0) for p in bookmaker_probs) / len(bookmaker_probs)

        # Re-normalise to ensure they sum to 1.
        total = home_p + away_p + draw_p
        if total == 0:
            return None

        return {
            "home": round(home_p / total, 3),
            "draw": round(draw_p / total, 3),
            "away": round(away_p / total, 3),
        }

    return None   # no matching event in the odds feed
