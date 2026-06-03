"""Fetch live results from API-Football and (re)score.

Re-seeding already updates match scores/status (idempotent), so a results
refresh is: fetch fixtures -> seed -> score. The Phase 6 scheduler will call
`refresh_and_score` periodically; admins can also trigger it on demand.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.services import football_api, scoring, seeding


def update_results(db: Session) -> dict:
    """Pull the latest fixtures/scores and upsert them. Returns seed stats."""
    raw = football_api.fetch_fixtures()
    normalized = football_api.normalize_fixtures(raw)
    return seeding.seed_world_cup(db, normalized)


def refresh_and_score(db: Session) -> dict:
    tournament = seeding.get_active_tournament(db)
    if tournament is None:
        return {"error": "no tournament seeded"}
    seed_stats = update_results(db)
    score_stats = scoring.score_tournament(db, tournament)
    return {**seed_stats, **score_stats}
