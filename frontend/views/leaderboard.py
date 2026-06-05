"""Leaderboard view: single table with match / awards / total columns.

Three sort views (tabs): Overall, Match predictions, Individual awards.
Each view re-ranks the table by that column independently.
"""
from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.labels import LEADERBOARD_VIEWS


def _movement(prev: int | None, cur_rank: int) -> str:
    if prev is None:
        return "—"
    diff = prev - cur_rank
    if diff > 0:
        return f"▲ {diff}"
    if diff < 0:
        return f"▼ {abs(diff)}"
    return "="


def render() -> None:
    st.header("🏆 Leaderboard")
    token = st.session_state["session_token"]
    me = st.session_state["user"]["id"]

    dash = api_client.get_dashboard(token)
    data = (dash or {}).get("leaderboard") or api_client.get_leaderboard(token)
    if data is None:
        st.info("Fixtures haven't been loaded yet — no standings to show.")
        return

    rows = data.get("rows", [])
    if not rows:
        st.caption("No players yet.")
        return

    tab_labels = list(LEADERBOARD_VIEWS.values())
    tab_keys = list(LEADERBOARD_VIEWS.keys())
    tabs = st.tabs(tab_labels)

    for tab, sort_key in zip(tabs, tab_keys):
        with tab:
            rank_key = f"{sort_key}_rank"
            sorted_rows = sorted(rows, key=lambda r: (r[rank_key], r["display_name"].lower()))

            table = [
                {
                    "Rank": r[rank_key],
                    "Mvmt": _movement(r.get("previous_rank"), r["total_pts_rank"])
                            if sort_key == "total_pts" else "—",
                    "Player": r["display_name"] + ("  ← you" if str(r["user_id"]) == me else ""),
                    "Match pts": r["match_pts"],
                    "Award pts": r["award_pts"],
                    "Total": r["total_pts"],
                }
                for r in sorted_rows
            ]
            st.dataframe(table, use_container_width=True, hide_index=True)

    st.caption("Movement (▲/▼) shown in Overall tab only — since last daily snapshot.")
