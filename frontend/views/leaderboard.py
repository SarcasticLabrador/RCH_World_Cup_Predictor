"""Leaderboard view: overall, per-stage, or specials, with ties shared."""
from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.labels import SCOPE_LABELS


def render() -> None:
    st.header("Leaderboard")
    token = st.session_state["session_token"]
    me = st.session_state["user"]["id"]

    scopes = list(SCOPE_LABELS.keys())
    scope = st.selectbox(
        "View", scopes, format_func=lambda s: SCOPE_LABELS[s], key="lb_scope"
    )

    data = api_client.get_leaderboard(token, scope)
    if data is None:
        st.info("Fixtures haven't been loaded yet — no standings to show.")
        return

    rows = data["rows"]
    if not rows:
        st.caption("No players yet.")
        return

    def movement(r: dict) -> str:
        prev = r.get("previous_rank")
        if prev is None:
            return "—"
        diff = prev - r["rank"]
        if diff > 0:
            return f"▲ {diff}"
        if diff < 0:
            return f"▼ {abs(diff)}"
        return "="

    table = [
        {
            "Rank": r["rank"],
            "": movement(r),
            "Player": r["display_name"] + ("  ← you" if r["user_id"] == me else ""),
            "Points": r["points"],
        }
        for r in rows
    ]
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.caption("Movement (▲/▼) is since the last daily snapshot.")
