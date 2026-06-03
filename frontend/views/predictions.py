"""My Predictions view: pick a stage, enter scorelines, save them."""
from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.labels import stage_label, STATE_LABELS, to_cet


def render() -> None:
    st.header("My Predictions")
    token = st.session_state["session_token"]

    windows = api_client.get_windows(token)
    if not windows:
        st.info("Fixtures haven't been loaded yet — nothing to predict right now.")
        return

    # Only stages that actually have fixtures (not 'pending').
    selectable = [w for w in windows if w["state"] != "pending"]
    if not selectable:
        st.info("No stages are available for predictions yet.")
        return

    labels = {f"{stage_label(w['stage'])}  ·  {STATE_LABELS[w['state']]}": w for w in selectable}
    # Default to the first open stage if any.
    default_idx = next((i for i, w in enumerate(selectable) if w["state"] == "open"), 0)
    choice = st.selectbox("Stage", list(labels.keys()), index=default_idx)
    window = labels[choice]
    stage = window["stage"]

    data = api_client.get_stage_fixtures(token, stage)
    if not data or not data["fixtures"]:
        st.warning("No fixtures found for this stage yet.")
        return

    state = data["state"]
    editable = state == "open"

    if not editable:
        st.info(f"This stage is **{STATE_LABELS[state]}** — predictions can't be changed.")
    else:
        st.caption(f"Closes: {to_cet(window['closes_at'])}. You can edit until then.")

    with st.form(f"predictions_{stage}"):
        inputs: dict[str, tuple] = {}
        for fx in data["fixtures"]:
            home = fx["home_team"] or "TBD"
            away = fx["away_team"] or "TBD"
            st.markdown(f"**{home} vs {away}**  \n*{to_cet(fx['kickoff_utc'])} — {fx['stadium'] or 'TBD'}*")
            c1, c2, c3 = st.columns([2, 1, 1])
            ph = fx["predicted_home_score"]
            pa = fx["predicted_away_score"]
            with c2:
                h = st.number_input(
                    f"{home}", min_value=0, max_value=30,
                    value=ph if ph is not None else 0,
                    key=f"h_{fx['match_id']}", disabled=not editable,
                )
            with c3:
                a = st.number_input(
                    f"{away}", min_value=0, max_value=30,
                    value=pa if pa is not None else 0,
                    key=f"a_{fx['match_id']}", disabled=not editable,
                )
            inputs[fx["match_id"]] = (int(h), int(a))
            st.divider()

        submitted = st.form_submit_button(
            "Save predictions", type="primary", disabled=not editable
        )

    if submitted and editable:
        items = [
            {"match_id": mid, "home_score": h, "away_score": a}
            for mid, (h, a) in inputs.items()
        ]
        try:
            resp = api_client.submit_predictions(token, stage, items)
            st.success(f"Saved {resp['saved']} prediction(s).")
        except Exception:
            st.error("Couldn't save predictions. The window may have just closed — try reloading.")
