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

    # --- Auth / Email (Phase 2) ---
    # Public base URL of the Streamlit app; magic-link URLs are built from it.
    app_base_url: str = "http://localhost:8501"
    # Email provider: "console" (dev: logs the link) or "brevo".
    email_provider: str = "console"
    brevo_api_key: str = ""
    # Verified single-sender address + display name (from Brevo single-sender).
    email_from: str = ""
    email_from_name: str = "World Cup Predictor"
    magic_link_ttl_hours: int = 24
    session_ttl_days: int = 30
    # Comma-separated whitelist; entries like "@acme.com" match any address on
    # that domain, full addresses match exactly.
    email_whitelist: str = ""
    # Comma-separated admin addresses; these users get is_admin=True on creation.
    admin_emails: str = ""
    # Secret used to sign session tokens (generate a long random string).
    secret_key: str = "change-me"

    # --- Results API (Phase 4) ---
    api_football_key: str = ""
    api_football_base_url: str = "https://v3.football.api-sports.io"
    # API-Football's league id for the FIFA World Cup is 1; season is the year.
    api_football_wc_league_id: int = 1
    api_football_season: int = 2026
    tournament_name: str = "FIFA World Cup 2026"

    # --- Gemini AI (Phase 7) ---
    gemini_api_key: str = ""
    # Default to a known-stable model; bump via env as newer models ship.
    gemini_model: str = "gemini-2.5-flash"
    # Configurable so you can move to a newer model without code changes.
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


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the .env file is parsed only once per process."""
    return Settings()
