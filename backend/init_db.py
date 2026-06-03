"""Standalone DB initialisation: create all tables.

Usage (from repo root):
    python -m backend.init_db

Safe to re-run: create_all only creates missing tables.
"""
from __future__ import annotations

from backend.config import get_settings
from backend.db.base import Base, engine

# Importing models registers them on Base.metadata so create_all sees them.
from backend.db import models  # noqa: F401


def main() -> None:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    tables = sorted(Base.metadata.tables.keys())
    print(f"Initialised database: {settings.database_url}")
    print(f"Created/verified {len(tables)} tables:")
    for t in tables:
        print(f"  - {t}")


if __name__ == "__main__":
    main()
