"""World Football Elo Ratings service.

Scrapes eloratings.net for current national team Elo ratings and converts
them to 3-way (home win / draw / away win) implied probabilities.

The draw probability model uses a piecewise function based on the Elo gap:
larger gaps mean fewer draws, matching historical international tournament data.

Caches the ratings for 24 hours in memory. If scraping fails for any reason,
returns an empty dict and the caller degrades gracefully.
"""
from __future__ import annotations

import logging
import time
import unicodedata
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Name normalisation                                                           #
# --------------------------------------------------------------------------- #

# eloratings.net name → our database name (FIFA official / wc2026_fixtures.py)
_ELO_NAME_MAP: dict[str, str] = {
    "usa":                    "united states",
    "korea republic":         "south korea",
    "ir iran":                "iran",
    "ivory coast":            "côte d'ivoire",
    "bosnia-herzegovina":     "bosnia & herzegovina",
    "cape verde":             "cape verde",
    "trinidad & tobago":      "trinidad and tobago",
    "antigua & barbuda":      "antigua and barbuda",
    "st. kitts & nevis":      "saint kitts and nevis",
    "china pr":               "china",
    "chinese taipei":         "taiwan",
    "guinea-bissau":          "guinea bissau",
}


def _norm(name: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", name.lower())
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(ascii_str.split())


def _canonical(name: str) -> str:
    n = _norm(name)
    return _ELO_NAME_MAP.get(n, n)


# --------------------------------------------------------------------------- #
# Scraping                                                                     #
# --------------------------------------------------------------------------- #

_CACHE: dict = {"ratings": {}, "fetched_at": 0.0}
_TTL = 24 * 3600   # 24 hours


def fetch_elo_ratings(force: bool = False) -> dict[str, float]:
    """Return {canonical_team_name: elo_rating} for all teams.

    Serves from cache within TTL. Returns {} on any failure.
    """
    now = time.time()
    if not force and _CACHE["ratings"] and now - _CACHE["fetched_at"] < _TTL:
        return _CACHE["ratings"]

    try:
        ratings = _scrape()
        _CACHE["ratings"] = ratings
        _CACHE["fetched_at"] = now
        log.info("Fetched %d Elo ratings from eloratings.net", len(ratings))
        return ratings
    except Exception as exc:
        log.warning("Elo scrape failed: %s — using cached or empty ratings", exc)
        return _CACHE["ratings"]   # stale cache is better than nothing


def _scrape() -> dict[str, float]:
    from bs4 import BeautifulSoup

    r = httpx.get(
        "https://www.eloratings.net/World",
        timeout=10,
        headers={"User-Agent": "Mozilla/5.0 (compatible; WCPredictor/1.0)"},
        follow_redirects=True,
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    ratings: dict[str, float] = {}

    # The page has a <table> with rows: rank | team | rating | +/- | high
    table = soup.find("table")
    if table is None:
        raise ValueError("No <table> found on eloratings.net")

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        try:
            name = cells[1].get_text(strip=True)
            rating = float(cells[2].get_text(strip=True).replace(",", ""))
            if name and rating > 0:
                ratings[_canonical(name)] = rating
        except (ValueError, IndexError):
            continue

    if len(ratings) < 50:
        raise ValueError(f"Too few ratings scraped ({len(ratings)}) — page structure may have changed")

    return ratings


# --------------------------------------------------------------------------- #
# Probability calculation                                                      #
# --------------------------------------------------------------------------- #

def _draw_probability(elo_gap: float) -> float:
    """Draw probability as a function of absolute Elo gap.

    Calibrated against historical FIFA World Cup data.
    """
    gap = abs(elo_gap)
    if gap < 50:
        return 0.27
    if gap < 100:
        return 0.25
    if gap < 200:
        return 0.22
    if gap < 300:
        return 0.18
    return 0.13


def elo_probabilities(
    home_team: str, away_team: str, ratings: dict[str, float]
) -> dict[str, float] | None:
    """Return {home, draw, away} probabilities from Elo ratings.

    Returns None if either team is not in the ratings dict.
    """
    h = ratings.get(_canonical(home_team))
    a = ratings.get(_canonical(away_team))
    if h is None or a is None:
        return None

    base_home = 1.0 / (1.0 + 10.0 ** ((a - h) / 400.0))
    draw = _draw_probability(h - a)
    scale = 1.0 - draw
    return {
        "home": round(base_home * scale, 3),
        "draw": round(draw, 3),
        "away": round((1.0 - base_home) * scale, 3),
    }
