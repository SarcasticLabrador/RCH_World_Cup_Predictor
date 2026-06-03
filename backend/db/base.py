"""Database engine, session factory and declarative base.

Also enables foreign-key enforcement on SQLite (off by default in SQLite),
which matters because the schema relies on FK constraints.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    pass


def _build_engine() -> Engine:
    connect_args = {}
    if settings.is_sqlite:
        # Ensure the parent directory (e.g. the persistent ./data volume) exists.
        db_path = settings.database_url.replace("sqlite:///", "", 1)
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # Streamlit + FastAPI can touch the connection from different threads.
        connect_args = {"check_same_thread": False}

    return create_engine(
        settings.normalized_database_url,
        connect_args=connect_args,
        echo=False,
        future=True,
        # Validates a pooled connection before use, so the first query after a
        # managed Postgres (e.g. Neon) auto-suspends doesn't fail on a stale
        # connection. Harmless for SQLite.
        pool_pre_ping=True,
    )


engine = _build_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@event.listens_for(Engine, "connect")
def _enable_sqlite_fk(dbapi_connection, _connection_record):
    """Turn on foreign-key enforcement for every SQLite connection."""
    # Only applies to SQLite; harmless to guard by checking for the pragma method.
    module_name = type(dbapi_connection).__module__
    if "sqlite3" in module_name:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db():
    """FastAPI dependency: yields a session and guarantees it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
