"""World Football Elo ratings, computed from the martj42 historical results dataset.

On first call, downloads the CSV from GitHub (open data, ~3.7 MB), processes
all matches from 2010 onwards using standard Elo update rules, and caches the
resulting ratings for 24 hours. Subsequent calls are instant.

If the download fails for any reason, returns an empty dict and the caller
degrades gracefully (ELO row simply doesn't appear in the fixture tile).
"""
from __future__ import annotations

import csv
import io
import logging
import time
import unicodedata

import httpx

log = logging.getLogger(__name__)

_CSV_URL = (
    "https://raw.githubusercontent.com/martj42/international_results"
    "/master/results.csv"
)
_CACHE: dict = {"ratings": {}, "fetched_at": 0.0}
_TTL = 24 * 3600


# --------------------------------------------------------------------------- #
# Name normalisation                                                           #
# --------------------------------------------------------------------------- #

def _norm(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name.lower())
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(ascii_str.split())


# CSV dataset name → our database name.
# Only entries where the two spellings genuinely differ.
_CSV_TO_DB: dict[str, str] = {
    "czech republic": "czechia",
    "turkey":         "turkiye",
    "ivory coast":    "côte d'ivoire",
}

# Reverse map with normalised keys so diacritics in DB names don't break lookup.
_DB_TO_CSV: dict[str, str] = {_norm(v): k for k, v in _CSV_TO_DB.items()}
# = {"czechia": "czech republic", "turkiye": "turkey", "cote d'ivoire": "ivory coast"}


def _lookup_key(db_name: str) -> str:
    """Convert a DB team name to the key used in the ratings dict."""
    n = _norm(db_name)
    return _DB_TO_CSV.get(n, n)


# --------------------------------------------------------------------------- #
# Elo computation                                                              #
# --------------------------------------------------------------------------- #

def _k_factor(tournament: str) -> float:
    t = tournament.lower()
    if "world cup" in t and "qualif" not in t:
        return 60.0
    if any(x in t for x in (
        "euro", "copa america", "afcon", "gold cup",
        "asian cup", "nations league", "confederation",
    )):
        return 50.0
    if "qualif" in t or "qualification" in t:
        return 40.0
    return 20.0   # friendlies


def _compute(csv_text: str) -> dict[str, float]:
    ratings: dict[str, float] = {}
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        if row["date"] < "2010":
            continue
        h_score, a_score = row["home_score"], row["away_score"]
        if not h_score or not a_score or h_score == "NA" or a_score == "NA":
            continue
        try:
            hs, as_ = int(h_score), int(a_score)
        except ValueError:
            continue

        home, away = _norm(row["home_team"]), _norm(row["away_team"])
        rh = ratings.get(home, 1500.0)
        ra = ratings.get(away, 1500.0)
        k = _k_factor(row["tournament"])

        eh = 1.0 / (1.0 + 10.0 ** ((ra - rh) / 400.0))
        sh = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)

        ratings[home] = rh + k * (sh - eh)
        ratings[away] = ra + k * ((1.0 - sh) - (1.0 - eh))

    return ratings


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

def fetch_elo_ratings(force: bool = False) -> dict[str, float]:
    """Return computed Elo ratings keyed by normalised CSV team names.

    Cached for 24 hours. Returns {} on failure.
    """
    now = time.time()
    if not force and _CACHE["ratings"] and now - _CACHE["fetched_at"] < _TTL:
        return _CACHE["ratings"]

    try:
        r = httpx.get(
            _CSV_URL, timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; WCPredictor/1.0)"},
        )
        r.raise_for_status()
        ratings = _compute(r.text)
        _CACHE["ratings"] = ratings
        _CACHE["fetched_at"] = now
        log.info("Computed %d Elo ratings from historical CSV", len(ratings))
        return ratings
    except Exception as exc:
        log.warning("Elo computation failed: %s — ELO display disabled", exc)
        return _CACHE["ratings"]


def _draw_probability(elo_gap: float) -> float:
    gap = abs(elo_gap)
    if gap < 50:   return 0.27
    if gap < 100:  return 0.25
    if gap < 200:  return 0.22
    if gap < 300:  return 0.18
    return 0.13


def elo_probabilities(
    home_team: str, away_team: str, ratings: dict[str, float]
) -> dict[str, float] | None:
    """Return {home, draw, away} implied probabilities.

    Returns None if either team is not in the ratings dict.
    """
    h_key = _lookup_key(home_team)
    a_key = _lookup_key(away_team)
    rh = ratings.get(h_key)
    ra = ratings.get(a_key)
    if rh is None or ra is None:
        return None

    base_home = 1.0 / (1.0 + 10.0 ** ((ra - rh) / 400.0))
    draw = _draw_probability(rh - ra)
    scale = 1.0 - draw
    return {
        "home": round(base_home * scale, 3),
        "draw": round(draw, 3),
        "away": round((1.0 - base_home) * scale, 3),
    }
