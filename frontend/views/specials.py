"""Individual awards and tournament stats predictions view."""
from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.labels import SPECIAL_LABELS, SPECIAL_ORDER, STATE_LABELS


def render() -> None:
    st.header("🏅 Individual awards")
    token = st.session_state["session_token"]

    data = api_client.get_specials(token)
    if data is None:
        st.error("Could not load picks. Is the backend running?")
        return

    state = data.get("state", "pending")
    editable = state == "open"
    current: dict[str, str] = data.get("predictions", {})

    teams_data = api_client.get_teams(token)
    team_names: list[str] = sorted(t["name"] for t in (teams_data or []))

    if not editable:
        st.info(f"Individual picks are **{STATE_LABELS.get(state, state)}**.")

    with st.form("specials_form"):
        chosen: dict[str, str] = {}

        st.subheader("Player awards")
        for key in ["golden_ball", "golden_boot", "golden_glove", "best_young_player"]:
            label, _ = SPECIAL_LABELS[key]
            chosen[key] = st.text_input(
                label,
                value=current.get(key, ""),
                disabled=not editable,
                key=f"spec_{key}",
                placeholder="Player name",
            )

        st.subheader("Team award")
        for key in ["team_most_goals"]:
            label, _ = SPECIAL_LABELS[key]
            options = [""] + team_names
            cur_val = current.get(key, "")
            idx = options.index(cur_val) if cur_val in options else 0
            chosen[key] = st.selectbox(
                label, options, index=idx, disabled=not editable, key=f"spec_{key}"
            )

        st.subheader("Tournament stats (closest prediction wins)")
        for key in ["total_goals", "yellow_cards", "red_cards", "fastest_goal", "biggest_margin"]:
            label, _ = SPECIAL_LABELS[key]
            cur_raw = current.get(key, "")
            cur_num = int(float(cur_raw)) if cur_raw else 0
            hint = " (exact minute)" if key == "fastest_goal" else ""
            val = st.number_input(
                f"{label}{hint}",
                min_value=0, max_value=9999,
                value=cur_num,
                disabled=not editable,
                key=f"spec_{key}",
            )
            chosen[key] = str(int(val))

        submitted = st.form_submit_button(
            "Save picks", type="primary", disabled=not editable
        )

    if submitted and editable:
        items = [{"category": k, "value": v} for k, v in chosen.items() if str(v).strip()]
        try:
            resp = api_client.submit_specials(token, items)
            st.success(f"Saved {resp['saved']} pick(s).")
        except Exception:
            st.error("Couldn't save — picks may have just locked.")

    if editable:
        st.divider()
        with st.expander("⚠️ Reset all individual award picks"):
            st.warning("This clears every pick you've made. Cannot be undone.")
            if st.checkbox("I understand", key="confirm_reset_specials"):
                if st.button("Reset all picks", key="do_reset_specials"):
                    try:
                        api_client.reset_specials(token)
                        st.success("All picks cleared.")
                        st.rerun()
                    except Exception as e:
                        if "409" in str(e):
                            st.error("Picks are locked.")
                        else:
                            st.error("Reset failed.")
