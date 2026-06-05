"""World Football Elo ratings service.

Ratings are computed from the martj42 historical results CSV and persisted
to the `elo_cache` table. This means they survive backend restarts and
Render redeploys — the expensive CSV download only runs once per week.

Refresh strategy:
  - On startup: pre-warm from the database if available, otherwise fetch.
  - Weekly: the scheduler calls `refresh_if_stale()` to re-fetch.
  - Fallback: if the database is unavailable, fall back to the in-memory
    module-level cache (populated once per process lifetime).

Public API:
  fetch_elo_ratings(db) -> dict[str, float]   — always returns ratings
  elo_probabilities(home, away, ratings) -> dict | None
  refresh_if_stale(db) -> bool                — called by scheduler
"""
from __future__ import annotations

import csv
import io
import logging
import time
import unicodedata
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

_CSV_URL = (
    "https://raw.githubusercontent.com/martj42/international_results"
    "/master/results.csv"
)

# In-memory fallback — used when DB is unavailable.
_MEM_CACHE: dict[str, float] = {}

# Refresh every 7 days.
_REFRESH_INTERVAL_DAYS = 7


# --------------------------------------------------------------------------- #
# Name normalisation                                                           #
# --------------------------------------------------------------------------- #

def _norm(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name.lower())
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(ascii_str.split())


# CSV dataset name → our database name (only entries that genuinely differ).
_CSV_TO_DB: dict[str, str] = {
    "czech republic":         "czechia",
    "turkey":                 "turkiye",
    "united states":          "usa",
    "bosnia and herzegovina": "bosnia & herzegovina",
}

# Reverse map with normalised keys to handle diacritics.
_DB_TO_CSV: dict[str, str] = {_norm(v): k for k, v in _CSV_TO_DB.items()}


def _lookup_key(db_name: str) -> str:
    """Convert a DB team name to the normalised key used in the ratings dict."""
    n = _norm(db_name)
    return _DB_TO_CSV.get(n, n)


# --------------------------------------------------------------------------- #
# Elo computation from CSV                                                     #
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
    return 20.0


def _compute_from_csv(csv_text: str) -> dict[str, float]:
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


def _fetch_and_compute() -> dict[str, float]:
    """Download the CSV and compute ratings. Raises on failure."""
    r = httpx.get(
        _CSV_URL, timeout=20,
        headers={"User-Agent": "Mozilla/5.0 (compatible; WCPredictor/1.0)"},
    )
    r.raise_for_status()
    return _compute_from_csv(r.text)


# --------------------------------------------------------------------------- #
# Database persistence                                                         #
# --------------------------------------------------------------------------- #

def _load_from_db(db: Session) -> dict[str, float]:
    """Read all cached ratings from the DB. Returns {} if table is empty."""
    from backend.db.models import EloCache
    rows = db.query(EloCache).all()
    return {r.team_key: r.rating for r in rows}


def _save_to_db(db: Session, ratings: dict[str, float]) -> None:
    """Upsert all ratings into the EloCache table."""
    from backend.db.models import EloCache
    now = datetime.now(timezone.utc)
    existing = {r.team_key: r for r in db.query(EloCache).all()}
    for key, rating in ratings.items():
        if key in existing:
            existing[key].rating = rating
            existing[key].fetched_at = now
        else:
            db.add(EloCache(team_key=key, rating=rating, fetched_at=now))
    db.commit()
    log.info("Saved %d ELO ratings to database", len(ratings))


def _db_age_days(db: Session) -> float | None:
    """Return how many days ago the DB cache was last written, or None if empty."""
    from backend.db.models import EloCache
    from sqlalchemy import func, select
    latest = db.scalar(select(func.max(EloCache.fetched_at)))
    if latest is None:
        return None
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - latest).total_seconds() / 86400


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

def fetch_elo_ratings(db: Session | None = None) -> dict[str, float]:
    """Return ELO ratings dict, using DB cache when available.

    Load order:
      1. DB cache (if db supplied and data exists and is fresh)
      2. Fetch from CSV + save to DB
      3. In-memory fallback (if DB unavailable)
    """
    global _MEM_CACHE

    if db is not None:
        try:
            age = _db_age_days(db)
            if age is not None and age < _REFRESH_INTERVAL_DAYS:
                ratings = _load_from_db(db)
                if ratings:
                    _MEM_CACHE = ratings
                    return ratings
            # DB empty or stale — fetch fresh.
            log.info("ELO cache stale or empty — fetching from CSV")
            ratings = _fetch_and_compute()
            _save_to_db(db, ratings)
            _MEM_CACHE = ratings
            return ratings
        except Exception as exc:
            log.warning("ELO DB operation failed (%s) — using memory cache", exc)

    # No DB or DB failed — use memory cache, fetching if empty.
    if not _MEM_CACHE:
        try:
            _MEM_CACHE = _fetch_and_compute()
        except Exception as exc:
            log.warning("ELO CSV fetch failed: %s", exc)
    return _MEM_CACHE


def refresh_if_stale(db: Session) -> bool:
    """Fetch fresh ratings if the DB cache is older than the refresh interval.

    Called by the weekly scheduler. Returns True if a refresh was performed.
    """
    try:
        age = _db_age_days(db)
        if age is None or age >= _REFRESH_INTERVAL_DAYS:
            ratings = _fetch_and_compute()
            _save_to_db(db, ratings)
            global _MEM_CACHE
            _MEM_CACHE = ratings
            log.info("ELO ratings refreshed (%d teams)", len(ratings))
            return True
        return False
    except Exception as exc:
        log.warning("ELO refresh failed: %s", exc)
        return False


# --------------------------------------------------------------------------- #
# Probability calculation                                                      #
# --------------------------------------------------------------------------- #

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
    """Return {home, draw, away} implied probabilities. None if team not found."""
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
