"""Admin view: enter results (group + bracket), set award actuals, account management."""
from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.labels import SPECIAL_LABELS, SPECIAL_ORDER, stage_label, to_cet


def _pen_expander(key_prefix: str) -> tuple[int | None, int | None, bool]:
    """Render a collapsed penalty expander; return (pen_home, pen_away, use_pens)."""
    with st.expander("Penalty shootout (if applicable)"):
        use = st.checkbox("Decided by penalties", key=f"{key_prefix}_use_pen")
        pc1, pc2 = st.columns(2)
        ph = pc1.number_input("Pen home", 0, 20, 0, key=f"{key_prefix}_ph")
        pa = pc2.number_input("Pen away", 0, 20, 0, key=f"{key_prefix}_pa")
    if use:
        return int(ph), int(pa), True
    return None, None, False


def render() -> None:
    user = st.session_state["user"]
    token = st.session_state["session_token"]
    if not user.get("is_admin"):
        st.error("Admin access required.")
        return

    st.header("⚙️ Admin")

    # ── Maintenance buttons ──────────────────────────────────────────────────
    st.subheader("Results & scoring")
    c1, c2 = st.columns(2)

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

    # ── Manual result entry ──────────────────────────────────────────────────
    st.subheader("Enter / override match results")
    group_tab, bracket_tab = st.tabs(["Group stage", "Knockout bracket"])

    with group_tab:
        windows = api_client.get_windows(token)
        stages = [w["stage"] for w in (windows or []) if w["state"] != "pending"]
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
                    c1, c2 = st.columns(2)
                    h = c1.number_input(home, 0, 30,
                        value=fx["home_score"] if fx["home_score"] is not None else 0,
                        key=f"ah_{fx['match_id']}")
                    a = c2.number_input(away, 0, 30,
                        value=fx["away_score"] if fx["away_score"] is not None else 0,
                        key=f"aa_{fx['match_id']}")
                    ph, pa, use_pen = _pen_expander(f"gpen_{fx['match_id']}")
                    finished = st.checkbox("Mark as played",
                        value=fx["home_score"] is not None,
                        key=f"af_{fx['match_id']}")
                    if st.button("Save", key=f"save_{fx['match_id']}", type="primary"):
                        try:
                            out = api_client.admin_set_match_result(
                                token, fx["match_id"], int(h), int(a), finished,
                                penalty_home=ph, penalty_away=pa,
                            )
                            st.success(f"Saved — {out['match_predictions_scored']} predictions scored.")
                        except Exception:
                            st.error("Couldn't save this result.")

    with bracket_tab:
        st.caption("Enter knockout results by FIFA match number (73 = first R32 match, 104 = Final).")
        data = api_client.get_bracket_slots(token)
        slots = (data or {}).get("slots", [])
        if not slots:
            st.info("No bracket slots seeded yet. Run the manual seed endpoint first.")
        else:
            from frontend.labels import STAGE_LABELS
            by_stage: dict[str, list] = {}
            for s in slots:
                by_stage.setdefault(s["stage"], []).append(s)

            for stage_key in ["r32", "r16", "qf", "sf", "final"]:
                stage_slots = sorted(by_stage.get(stage_key, []), key=lambda s: s["match_number"])
                if not stage_slots:
                    continue
                st.markdown(f"**{STAGE_LABELS.get(stage_key, stage_key)}**")
                for sl in stage_slots:
                    home = sl.get("home_team") or sl["home_descriptor"]
                    away = sl.get("away_team") or sl["away_descriptor"]
                    label = f"M{sl['match_number']}: {home} vs {away}"
                    with st.expander(label):
                        c1, c2 = st.columns(2)
                        h = c1.number_input(home, 0, 30,
                            value=sl["home_score"] if sl["home_score"] is not None else 0,
                            key=f"bh_{sl['match_number']}")
                        a = c2.number_input(away, 0, 30,
                            value=sl["away_score"] if sl["away_score"] is not None else 0,
                            key=f"ba_{sl['match_number']}")
                        ph, pa, use_pen = _pen_expander(f"bpen_{sl['match_number']}")
                        finished = st.checkbox("Mark as played",
                            value=sl["status"] == "finished",
                            key=f"bf_{sl['match_number']}")
                        if st.button("Save", key=f"bsave_{sl['match_number']}", type="primary"):
                            try:
                                out = api_client.admin_set_bracket_result(
                                    token, sl["match_number"], int(h), int(a), finished,
                                    penalty_home=ph, penalty_away=pa,
                                )
                                st.success(f"Saved — {out['match_predictions_scored']} predictions scored.")
                            except Exception:
                                st.error("Couldn't save this result.")

    st.divider()

    # ── Award actuals ────────────────────────────────────────────────────────
    st.subheader("Award results (manually entered)")
    st.caption(
        "Enter the actual winner for each award or stat. "
        "Numeric categories (Total goals, Yellow cards, etc.) take a number. "
        "Once saved the scoring engine re-runs immediately."
    )

    cat_keys = [c for c in SPECIAL_ORDER if c in SPECIAL_LABELS]

    def _fmt(key: str) -> str:
        label, kind = SPECIAL_LABELS[key]
        return f"{label}  [{kind}]"

    category = st.selectbox("Category", cat_keys, format_func=_fmt, key="admin_special_cat")
    _, kind = SPECIAL_LABELS[category]
    if kind == "number":
        num_val = st.number_input("Actual value", min_value=0, max_value=9999, key="admin_special_num")
        value = str(int(num_val))
    else:
        value = st.text_input("Actual winner (player or team name)", key="admin_special_val")

    if st.button("Save award result", type="primary"):
        if str(value).strip():
            try:
                out = api_client.admin_set_special_result(token, category, str(value).strip())
                st.success(f"Saved — {out['special_predictions_scored']} predictions scored.")
            except Exception:
                st.error("Couldn't save this result.")
        else:
            st.warning("Enter a value first.")

    st.divider()

    # ── Account management ───────────────────────────────────────────────────
    st.subheader("Account management")
    tab1, tab2 = st.tabs(["Reset password", "Create account"])

    with tab1:
        st.caption("Reset a colleague's password on their behalf.")
        rp_email = st.text_input("Email address", key="rp_email")
        rp_pw = st.text_input("New password (min 8 chars)", type="password", key="rp_pw")
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
                    st.error("No account found." if "404" in str(e) else "Reset failed.")

    with tab2:
        st.caption("Create an account on behalf of a colleague. Bypasses the whitelist.")
        cu_name = st.text_input("Display name", key="cu_name")
        cu_email = st.text_input("Email address", key="cu_email")
        cu_pw = st.text_input("Password (min 8 chars)", type="password", key="cu_pw")
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
                    st.error("Email already in use." if "409" in str(e) else "Account creation failed.")


    st.divider()
    st.subheader("🔒 Prediction lock")
    st.caption(
        "When locked, no user can submit or modify any prediction — "
        "group stage, knockout bracket, or individual awards. "
        "You can unlock at any time if needed."
    )
    dash = api_client.get_dashboard(token) or {}
    # Read current lock state from the tournament (fall back to unlocked).
    currently_locked = False  # dashboard doesn't expose this yet; rely on toggle feedback

    col_lock, col_unlock = st.columns(2)
    if col_lock.button("🔒 Lock all predictions", key="do_lock", type="primary"):
        try:
            out = api_client.admin_set_predictions_lock(token, locked=True)
            if hasattr(api_client.get_dashboard, "clear"):
                api_client.get_dashboard.clear()
            st.success("All predictions are now locked.")
        except Exception as e:
            st.error(f"Failed: {e}")

    if col_unlock.button("🔓 Unlock all predictions", key="do_unlock"):
        try:
            out = api_client.admin_set_predictions_lock(token, locked=False)
            if hasattr(api_client.get_dashboard, "clear"):
                api_client.get_dashboard.clear()
            st.success("Predictions are now unlocked.")
        except Exception as e:
            st.error(f"Failed: {e}")

    st.divider()
    st.subheader("⚠️ Clear all match results")
    st.caption(
        "Resets every group stage match and knockout slot back to 'scheduled' with no scores. "
        "All awarded points are also nullified. Predictions are NOT affected."
    )
    with st.expander("Clear all results (irreversible)"):
        st.warning("This wipes all real match results and resets all points. Cannot be undone.")
        if st.checkbox("I understand — clear everything", key="confirm_clear_results"):
            if st.button("Clear all results now", key="do_clear_results", type="primary"):
                try:
                    out = api_client.admin_clear_results(token)
                    st.success(
                        f"Cleared {out['matches_cleared']} group matches "
                        f"and {out['slots_cleared']} bracket slots."
                    )
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.divider()
    st.subheader("Team stats (computed)")
    try:
        stats = api_client.admin_team_stats(token)
        if stats:
            st.dataframe(stats, use_container_width=True, hide_index=True)
        else:
            st.caption("No finished matches yet.")
    except Exception:
        st.caption("Stats unavailable.")
