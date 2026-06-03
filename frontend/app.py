"""Streamlit app entrypoint.

Sets up the import path once, gates on login (magic-link), captures a
display name on first login, then exposes the multi-page app via
st.navigation. Later phases add more pages (leaderboard, fixtures, AI, admin).
"""
from __future__ import annotations

import pathlib
import sys

# Ensure the repo root is importable (so `from frontend...`/`backend...` work)
# regardless of how Streamlit launches this script.
_here = pathlib.Path(__file__).resolve()
for _parent in _here.parents:
    if (_parent / "frontend").is_dir() and (_parent / "backend").is_dir():
        sys.path.insert(0, str(_parent))
        break

import streamlit as st  # noqa: E402

from frontend import api_client  # noqa: E402
from frontend.auth import logout, require_login  # noqa: E402
from frontend.views import home as home_view  # noqa: E402
from frontend.views import predictions as predictions_view  # noqa: E402
from frontend.views import specials as specials_view  # noqa: E402
from frontend.views import leaderboard as leaderboard_view  # noqa: E402
from frontend.views import match_centre as match_centre_view  # noqa: E402
from frontend.views import admin as admin_view  # noqa: E402

st.set_page_config(page_title="World Cup 2026 Predictor", page_icon="⚽", layout="centered")

# --- Login gate (renders the login form and stops the page if signed out) ---
user = require_login()

# --- First-time display-name capture ---
if not user.get("display_name"):
    st.title("⚽ World Cup 2026 Predictor")
    st.info("Welcome! Choose a display name for the leaderboard.")
    name = st.text_input("Display name", key="display_name_input")
    if st.button("Save", type="primary") and name.strip():
        st.session_state["user"] = api_client.update_profile(
            st.session_state["session_token"], name.strip()
        )
        st.rerun()
    st.stop()

# --- Sidebar account box ---
with st.sidebar:
    st.markdown(f"**{user['display_name']}**")
    st.caption(user["email"] + ("  ·  🔑 admin" if user.get("is_admin") else ""))
    if st.button("Log out"):
        logout()
        st.rerun()

# --- Navigation across views ---
pages = [
    st.Page(home_view.render, title="Home", icon="🏠", default=True),
    st.Page(predictions_view.render, title="My Predictions", icon="🔮"),
    st.Page(specials_view.render, title="My Picks", icon="🏅"),
    st.Page(leaderboard_view.render, title="Leaderboard", icon="🏆"),
    st.Page(match_centre_view.render, title="AI Match Centre", icon="🤖"),
]
if user.get("is_admin"):
    pages.append(st.Page(admin_view.render, title="Admin", icon="⚙️"))
st.navigation(pages).run()
