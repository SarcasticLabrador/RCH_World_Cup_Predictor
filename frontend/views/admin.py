"""Admin view: enter results, set award winners, refresh from API, re-score."""
from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.labels import SPECIAL_LABELS, stage_label, to_cet


def render() -> None:
    user = st.session_state["user"]
    token = st.session_state["session_token"]
    if not user.get("is_admin"):
        st.error("Admin access required.")
        return

    st.header("⚙️ Admin")

    # --- Maintenance ---
    st.subheader("Results & scoring")
    c1, c2 = st.columns(2)
    if c1.button("🔄 Refresh results from API-Football"):
        try:
            out = api_client.admin_refresh_results(token)
            st.success(f"Refreshed. {out}")
        except Exception:
            st.error("Refresh failed — check the API key on the server.")
    if c2.button("♻️ Re-score now"):
        try:
            out = api_client.admin_rescore(token)
            st.success(f"Re-scored: {out}")
        except Exception:
            st.error("Re-score failed.")

    c3, c4 = st.columns(2)
    if c3.button("🛠️ Run maintenance now"):
        try:
            out = api_client.admin_run_maintenance(token)
            st.success(f"Maintenance: {out}")
        except Exception:
            st.error("Maintenance run failed.")
    if c4.button("📸 Take leaderboard snapshot"):
        try:
            out = api_client.admin_snapshot(token)
            st.success(f"Snapshot saved ({out.get('snapshot_rows', 0)} rows).")
        except Exception:
            st.error("Snapshot failed.")

    st.divider()

    # --- Manual result entry ---
    st.subheader("Enter / override match results")
    windows = api_client.get_windows(token)
    stages = [w["stage"] for w in windows if w["state"] != "pending"]
    if not stages:
        st.info("No fixtures available yet.")
    else:
        stage = st.selectbox(
            "Stage", stages, format_func=stage_label, key="admin_stage"
        )
        data = api_client.get_stage_fixtures(token, stage)
        fixtures = (data or {}).get("fixtures", [])
        for fx in fixtures:
            home = fx["home_team"] or "TBD"
            away = fx["away_team"] or "TBD"
            with st.expander(f"{home} vs {away} — {to_cet(fx['kickoff_utc'])}"):
                hc, ac, fc = st.columns([1, 1, 1])
                h = hc.number_input(
                    f"{home}", min_value=0, max_value=30,
                    value=fx["home_score"] if fx["home_score"] is not None else 0,
                    key=f"ah_{fx['match_id']}",
                )
                a = ac.number_input(
                    f"{away}", min_value=0, max_value=30,
                    value=fx["away_score"] if fx["away_score"] is not None else 0,
                    key=f"aa_{fx['match_id']}",
                )
                finished = fc.checkbox(
                    "Played", value=fx["home_score"] is not None,
                    key=f"af_{fx['match_id']}",
                )
                if st.button("Save result", key=f"save_{fx['match_id']}"):
                    try:
                        out = api_client.admin_set_match_result(
                            token, fx["match_id"], int(h), int(a), finished
                        )
                        st.success(f"Saved & re-scored: {out}")
                    except Exception:
                        st.error("Couldn't save this result.")

    st.divider()

    # --- Award / special results ---
    st.subheader("Award winners & overrides")
    st.caption(
        "Champion, runner-up and the two team-stat categories are derived "
        "automatically from results — set them here only to override. The four "
        "player awards must be entered manually."
    )
    cat_keys = list(SPECIAL_LABELS.keys())

    def _fmt(key: str) -> str:
        label, kind = SPECIAL_LABELS[key]
        return f"{label} ({'auto' if kind == 'auto' else 'manual'})"

    category = st.selectbox("Category", cat_keys, format_func=_fmt, key="admin_special_cat")
    value = st.text_input("Actual winner (team or player name)", key="admin_special_val")
    if st.button("Save winner", type="primary"):
        if value.strip():
            try:
                out = api_client.admin_set_special_result(token, category, value.strip())
                st.success(f"Saved & re-scored: {out}")
            except Exception:
                st.error("Couldn't save this winner.")
        else:
            st.warning("Enter a name first.")

    st.divider()

    # --- Team stats (transparency) ---
    st.subheader("Team stats (computed)")
    try:
        stats = api_client.admin_team_stats(token)
        if stats:
            st.dataframe(stats, use_container_width=True, hide_index=True)
        else:
            st.caption("No finished matches yet.")
    except Exception:
        st.caption("Stats unavailable.")
