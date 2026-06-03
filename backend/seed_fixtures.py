"""Seed fixtures from API-Football (live).

Usage (from repo root, with API_FOOTBALL_KEY set in .env):
    python -m backend.seed_fixtures

Idempotent: safe to re-run as the schedule firms up and knockout teams resolve.
"""
from __future__ import annotations

from backend.db.base import Base, SessionLocal, engine
from backend.db import models  # noqa: F401  (register tables)
from backend.services import football_api, seeding


def main() -> None:
    Base.metadata.create_all(bind=engine)

    raw_fixtures = football_api.fetch_fixtures()
    print(f"Fetched {len(raw_fixtures)} raw fixtures from API-Football.")
    if not raw_fixtures:
        print("No fixtures returned. Check API_FOOTBALL_KEY, league id and season.")
        return

    try:
        groups = football_api.extract_groups(football_api.fetch_standings())
        print(f"Resolved group letters for {len(groups)} teams.")
    except Exception as exc:  # standings are optional
        groups = {}
        print(f"Standings unavailable ({exc}); seeding without group letters.")

    normalized = football_api.normalize_fixtures(raw_fixtures)
    db = SessionLocal()
    try:
        stats = seeding.seed_world_cup(db, normalized, groups)
        db.commit()
    finally:
        db.close()

    print("Seeding complete:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
