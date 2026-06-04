"""Streamlit app entrypoint."""
from __future__ import annotations

import os
import pathlib
import sys

_here = pathlib.Path(__file__).resolve()
for _parent in _here.parents:
    if (_parent / "frontend").is_dir() and (_parent / "backend").is_dir():
        sys.path.insert(0, str(_parent))
        break

import streamlit as st

try:
    _backend = st.secrets.get("BACKEND_URL")
    if _backend:
        os.environ.setdefault("BACKEND_URL", str(_backend))
except Exception:
    pass

from frontend import api_client
from frontend.auth import logout, require_login
from frontend.views import admin as admin_view
from frontend.views import fixtures as fixtures_view
from frontend.views import home as home_view
from frontend.views import leaderboard as leaderboard_view
from frontend.views import match_centre as match_centre_view
from frontend.views import predictions as predictions_view
from frontend.views import specials as specials_view

st.set_page_config(page_title="World Cup 2026 Predictor", page_icon="⚽", layout="centered")

user = require_login()

# First-time display-name capture
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

# Sidebar: account info + navigation
pages = {
    "🏠 Home": home_view.render,
    "📅 Fixtures & Results": fixtures_view.render,
    "🔮 Match predictions": predictions_view.render,
    "🏅 Individual awards": specials_view.render,
    "🏆 Leaderboard": leaderboard_view.render,
    "📰 Football news update (Experimental)": match_centre_view.render,
}
if user.get("is_admin"):
    pages["⚙️ Admin"] = admin_view.render

with st.sidebar:
    st.markdown(f"**{user['display_name']}**")
    st.caption(user["email"] + ("  ·  🔑 admin" if user.get("is_admin") else ""))
    if st.button("Log out"):
        logout()
        st.rerun()
    st.divider()
    selection = st.radio("", list(pages.keys()), label_visibility="collapsed")

pages[selection]()
