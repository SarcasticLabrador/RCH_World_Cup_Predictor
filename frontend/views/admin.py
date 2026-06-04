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

    # --- Account management ---
    st.subheader("Account management")
    tab1, tab2 = st.tabs(["Reset password", "Create account"])

    with tab1:
        st.caption("Reset a colleague's password on their behalf.")
        rp_email = st.text_input("Email address", key="rp_email")
        rp_pw = st.text_input("New password (min 8 characters)", type="password", key="rp_pw")
        if st.button("Reset password", key="rp_btn", type="primary"):
            if not rp_email or not rp_pw:
                st.warning("Fill in both fields.")
            elif len(rp_pw) < 8:
                st.warning("Password must be at least 8 characters.")
            else:
                try:
                    api_client.admin_reset_password(token, rp_email.strip(), rp_pw)
                    st.success(f"Password reset for {rp_email}.")
                except Exception as e:
                    msg = str(e)
                    if "404" in msg:
                        st.error("No account found with that email.")
                    else:
                        st.error("Reset failed — please try again.")

    with tab2:
        st.caption("Create an account on behalf of a colleague. Bypasses the email whitelist.")
        cu_name = st.text_input("Display name", key="cu_name")
        cu_email = st.text_input("Email address", key="cu_email")
        cu_pw = st.text_input("Password (min 8 characters)", type="password", key="cu_pw")
        cu_admin = st.checkbox("Grant admin rights", key="cu_admin")
        if st.button("Create account", key="cu_btn", type="primary"):
            if not cu_name or not cu_email or not cu_pw:
                st.warning("Fill in all fields.")
            elif len(cu_pw) < 8:
                st.warning("Password must be at least 8 characters.")
            else:
                try:
                    result = api_client.admin_create_user(token, cu_email.strip(), cu_pw, cu_name.strip(), cu_admin)
                    st.success(f"Account created for {result['display_name']} ({result['email']}).")
                except Exception as e:
                    msg = str(e)
                    if "409" in msg:
                        st.error("An account with that email already exists.")
                    else:
                        st.error("Account creation failed — please try again.")
    st.subheader("Team stats (computed)")
    try:
        stats = api_client.admin_team_stats(token)
        if stats:
            st.dataframe(stats, use_container_width=True, hide_index=True)
        else:
            st.caption("No finished matches yet.")
    except Exception:
        st.caption("Stats unavailable.")
