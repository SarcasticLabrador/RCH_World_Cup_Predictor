"""Thin HTTP client for the backend API, used by the Streamlit app."""
from __future__ import annotations

import os

import httpx
import streamlit as st


def _resolve_backend_url() -> str:
    """Backend base URL from env (local) or Streamlit secrets (Streamlit Cloud)."""
    url = os.getenv("BACKEND_URL")
    if not url:
        try:
            import streamlit as st

            url = st.secrets.get("BACKEND_URL")  # type: ignore[attr-defined]
        except Exception:
            url = None
    return (url or "http://localhost:8000").rstrip("/")


BACKEND_URL = _resolve_backend_url()
_TIMEOUT = 15.0


def register(email: str, password: str, display_name: str) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def login(email: str, password: str) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/auth/login",
        json={"email": email, "password": password},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def _auth_headers(session_token: str) -> dict:
    return {"Authorization": f"Bearer {session_token}"}


def get_me(session_token: str) -> dict | None:
    r = httpx.get(f"{BACKEND_URL}/auth/me", headers=_auth_headers(session_token), timeout=_TIMEOUT)
    if r.status_code == 401:
        return None
    r.raise_for_status()
    return r.json()


def update_profile(session_token: str, display_name: str) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/auth/me",
        json={"display_name": display_name},
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


# --- Predictions (Phase 3) ---

@st.cache_data(ttl=300, show_spinner=False)
def get_windows(session_token: str) -> list[dict]:
    r = httpx.get(
        f"{BACKEND_URL}/predictions/windows",
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    if r.status_code == 404:  # nothing seeded yet
        return []
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=120, show_spinner=False)

@st.cache_data(ttl=120, show_spinner=False)
def get_dashboard(session_token: str) -> dict | None:
    try:
        r = httpx.get(
            f"{BACKEND_URL}/dashboard",
            headers=_auth_headers(session_token),
            timeout=20.0,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def get_stage_fixtures(session_token: str, stage: str) -> dict | None:
    r = httpx.get(
        f"{BACKEND_URL}/predictions/fixtures",
        params={"stage": stage},
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def submit_predictions(session_token: str, stage: str, items: list[dict]) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/predictions",
        json={"stage": stage, "predictions": items},
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def reset_predictions(session_token: str, stage: str, group: str | None = None) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/predictions/reset",
        json={"stage": stage, "group": group},
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def reset_specials(session_token: str) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/specials/reset",
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


# --- Admin (Phase 4) ---

def admin_set_match_result(
    session_token: str,
    match_id: str,
    home: int,
    away: int,
    finished: bool = True,
    penalty_home: int | None = None,
    penalty_away: int | None = None,
) -> dict:
    payload: dict = {
        "match_id": match_id,
        "home_score": home,
        "away_score": away,
        "finished": finished,
    }
    if penalty_home is not None:
        payload["penalty_home_score"] = penalty_home
        payload["penalty_away_score"] = penalty_away
    r = httpx.post(
        f"{BACKEND_URL}/admin/match-result",
        json=payload,
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def admin_set_bracket_result(
    session_token: str,
    match_number: int,
    home: int,
    away: int,
    finished: bool = True,
    penalty_home: int | None = None,
    penalty_away: int | None = None,
) -> dict:
    payload: dict = {
        "match_number": match_number,
        "home_score": home,
        "away_score": away,
        "finished": finished,
    }
    if penalty_home is not None:
        payload["penalty_home_score"] = penalty_home
        payload["penalty_away_score"] = penalty_away
    r = httpx.post(
        f"{BACKEND_URL}/bracket/admin/result",
        json=payload,
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def admin_set_special_result(session_token: str, category: str, value: str) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/admin/special-result",
        json={"category": category, "actual_value": value},
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def admin_rescore(session_token: str) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/admin/rescore",
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def admin_run_maintenance(session_token: str) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/admin/run-maintenance",
        headers=_auth_headers(session_token),
        timeout=120.0,
    )
    r.raise_for_status()
    return r.json()


def admin_snapshot(session_token: str) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/admin/snapshot",
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def admin_reset_password(session_token: str, email: str, new_password: str) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/admin/reset-password",
        json={"email": email, "new_password": new_password},
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def admin_create_user(
    session_token: str, email: str, password: str, display_name: str, is_admin: bool = False
) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/admin/create-user",
        json={"email": email, "password": password, "display_name": display_name, "is_admin": is_admin},
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def admin_team_stats(session_token: str) -> list[dict]:
    r = httpx.get(
        f"{BACKEND_URL}/admin/team-stats",
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


# --- Specials & leaderboard (Phase 5) ---

def get_specials(session_token: str) -> dict | None:
    r = httpx.get(
        f"{BACKEND_URL}/specials", headers=_auth_headers(session_token), timeout=_TIMEOUT
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def submit_specials(session_token: str, items: list[dict]) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/specials",
        json={"predictions": items},
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=3600, show_spinner=False)
def get_teams(session_token: str) -> list[dict]:
    r = httpx.get(
        f"{BACKEND_URL}/specials/teams",
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=120, show_spinner=False)
def get_leaderboard(session_token: str) -> dict | None:
    r = httpx.get(
        f"{BACKEND_URL}/leaderboard",
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def get_match_centre(session_token: str, news: bool = False, refresh: bool = False) -> dict | None:
    r = httpx.get(
        f"{BACKEND_URL}/ai/match-centre",
        params={"news": news, "refresh": refresh},
        headers=_auth_headers(session_token),
        timeout=60.0,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=120, show_spinner=False)
def get_bracket_slots(session_token: str) -> dict | None:
    try:
        r = httpx.get(
            f"{BACKEND_URL}/bracket/slots",
            headers=_auth_headers(session_token),
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def submit_bracket_predictions(session_token: str, items: list[dict]) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/bracket/predictions",
        json={"predictions": items},
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()



@st.cache_data(ttl=600, show_spinner=False)
def get_odds(session_token: str) -> dict | None:
    try:
        r = httpx.get(
            f"{BACKEND_URL}/odds",
            headers=_auth_headers(session_token),
            timeout=15.0,   # ELO scrape can take a moment on first call
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def admin_clear_results(session_token: str) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/admin/clear-results",
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def admin_set_predictions_lock(session_token: str, locked: bool) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/admin/lock-predictions",
        params={"locked": str(locked).lower()},
        headers=_auth_headers(session_token),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def admin_rescore_preview(session_token: str) -> dict:
    r = httpx.post(
        f"{BACKEND_URL}/admin/rescore-preview",
        headers=_auth_headers(session_token),
        timeout=60.0,   # per-user bracket derivation can take a moment
    )
    r.raise_for_status()
    return r.json()
