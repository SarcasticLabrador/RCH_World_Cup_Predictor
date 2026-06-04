"""My Picks view: champion, runner-up, awards and team-stat predictions."""
from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.labels import SPECIAL_LABELS, STATE_LABELS, TEAM_SPECIALS


def render() -> None:
    st.header("🏅 My Picks")
    st.caption(
        "Champion (25 pts), runner-up (10 pts) and the awards/team stats "
        "(10 pts each). These lock when the first group match kicks off."
    )
    token = st.session_state["session_token"]

    data = api_client.get_specials(token)
    if data is None:
        st.info("Fixtures haven't been loaded yet — picks open once they are.")
        return

    state = data["state"]
    if state == "pending":
        st.info("Picks aren't open yet.")
        return

    current = data["predictions"]
    editable = state == "open"
    if not editable:
        st.info(f"Picks are **{STATE_LABELS.get(state, state)}** and can't be changed.")

    teams = [t["name"] for t in api_client.get_teams(token)]
    team_options = ["—"] + teams

    with st.form("specials_form"):
        chosen: dict[str, str] = {}
        for category in data["categories"]:
            label = SPECIAL_LABELS.get(category, (category, ""))[0]
            existing = current.get(category, "")
            if category in TEAM_SPECIALS and teams:
                idx = team_options.index(existing) if existing in team_options else 0
                pick = st.selectbox(
                    label, team_options, index=idx,
                    key=f"sp_{category}", disabled=not editable,
                )
                chosen[category] = "" if pick == "—" else pick
            else:
                chosen[category] = st.text_input(
                    label, value=existing, key=f"sp_{category}",
                    disabled=not editable, placeholder="Player name",
                )

        submitted = st.form_submit_button(
            "Save picks", type="primary", disabled=not editable
        )

    if submitted and editable:
        items = [{"category": c, "value": v} for c, v in chosen.items() if v.strip()]
        try:
            resp = api_client.submit_specials(token, items)
            st.success(f"Saved {resp['saved']} pick(s).")
        except Exception:
            st.error("Couldn't save — picks may have just locked. Try reloading.")

    if editable:
        st.divider()
        with st.expander("⚠️ Reset all individual award picks"):
            st.warning("This clears every pick you've made. Cannot be undone.")
            confirmed = st.checkbox("I understand", key="confirm_reset_specials")
            if st.button("Reset all picks", disabled=not confirmed, key="do_reset_specials"):
                try:
                    api_client.reset_specials(token)
                    st.success("All picks cleared.")
                    st.rerun()
                except Exception as e:
                    if "409" in str(e):
                        st.error("Picks are locked and can no longer be reset.")
                    else:
                        st.error("Reset failed — please try again.")
