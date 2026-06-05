"""Application configuration, loaded from environment / .env file.

Centralises all settings so later phases (auth, results API, Gemini) only need
to add fields here rather than scattering os.getenv calls across the codebase.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core ---
    app_name: str = "FIFA World Cup 2026 Predictor"
    environment: str = "development"
    database_url: str = "sqlite:///./data/worldcup.db"

    # --- Auth (Phase 2) ---
    app_base_url: str = "http://localhost:8501"
    session_ttl_days: int = 30
    # Comma-separated whitelist; entries like "@acme.com" match any address on
    # that domain, full addresses match exactly.
    email_whitelist: str = ""
    # Comma-separated admin addresses; these users get is_admin=True on creation.
    admin_emails: str = ""
    # Secret used to sign session tokens (generate a long random string).
    secret_key: str = "change-me"

    tournament_name: str = "FIFA World Cup 2026"

    # --- Odds & ELO (Phase 9) ---
    # Free tier: 500 requests/month. Leave empty to disable market odds display.
    odds_api_key: str = ""
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"

    # --- Gemini AI (Phase 7) ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # --- Scheduler & tasks (Phase 6) ---
    # In-process scheduler (needs an always-on backend). Disable if you instead
    # drive maintenance/snapshots via an external cron hitting /tasks/*.
    scheduler_enabled: bool = True
    results_poll_minutes: int = 120
    # Daily leaderboard snapshot time, in CET/CEST (Europe/Berlin).
    snapshot_hour_cet: int = 6
    # Shared secret for the /tasks/* endpoints (external cron). Empty = disabled.
    task_token: str = ""

    @property
    def whitelist_entries(self) -> list[str]:
        """Whitelist parsed into a clean list (domains like '@acme.com' or full addresses)."""
        return [e.strip().lower() for e in self.email_whitelist.split(",") if e.strip()]

    @property
    def admin_email_entries(self) -> list[str]:
        """Admin addresses parsed into a clean list."""
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def normalized_database_url(self) -> str:
        """Use the psycopg (v3) driver for Postgres URLs.

        Managed providers (Neon, Supabase) hand out 'postgresql://...' URLs,
        which SQLAlchemy maps to psycopg2 by default. We ship psycopg v3, so
        rewrite the scheme to 'postgresql+psycopg://' transparently.
        """
        url = self.database_url
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]
        if url.startswith("postgres://"):  # some providers use this alias
            return "postgresql+psycopg://" + url[len("postgres://"):]
        return url


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the .env file is parsed only once per process."""
    return Settings()
