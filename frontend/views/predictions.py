"""Match predictions view: group-based layout for group stage, reset support."""
from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.flags import GROUP_MAP, get_flag
from frontend.labels import STATE_LABELS, stage_label, to_cet

GROUPS = list("ABCDEFGHIJKL")


def _reset_expander(token: str, stage: str, group: str | None, label: str) -> None:
    """Collapsible reset control with an 'I understand' confirmation checkbox."""
    key_suffix = f"{stage}_{group or 'all'}"
    with st.expander(f"⚠️ Reset {label}"):
        st.warning("This permanently clears the selected predictions and cannot be undone.")
        confirmed = st.checkbox("I understand", key=f"confirm_{key_suffix}")
        if st.button("Reset", key=f"do_reset_{key_suffix}", disabled=not confirmed):
            try:
                api_client.reset_predictions(token, stage, group)
                st.success("Predictions cleared.")
                st.rerun()
            except Exception as e:
                if "409" in str(e):
                    st.error("This prediction window is locked and can no longer be reset.")
                else:
                    st.error("Reset failed — please try again.")


def _render_group_stage(token: str, state: str) -> None:
    editable = state == "open"
    if not editable:
        st.info(f"Group stage predictions are **{STATE_LABELS.get(state, state)}** — no changes allowed.")

    data = api_client.get_stage_fixtures(token, "group")
    if not data or not data.get("fixtures"):
        st.info("No group stage fixtures loaded yet.")
        return

    all_fixtures = data["fixtures"]

    # Split into per-group lists
    by_group: dict[str, list] = {g: [] for g in GROUPS}
    for fx in all_fixtures:
        grp = GROUP_MAP.get(fx.get("home_team") or "") or GROUP_MAP.get(fx.get("away_team") or "")
        if grp:
            by_group[grp].append(fx)

    # Global reset at the top
    if editable:
        _reset_expander(token, "group", None, "ALL group stage predictions")
        st.divider()

    tabs = st.tabs([f"Group {g}" for g in GROUPS])
    for tab, group in zip(tabs, GROUPS):
        with tab:
            fixtures = sorted(by_group[group], key=lambda f: f["kickoff_utc"])
            if not fixtures:
                st.caption("No fixtures for this group yet.")
                continue

            with st.form(f"preds_group_{group}"):
                inputs: dict[str, tuple] = {}
                for fx in fixtures:
                    home = fx["home_team"] or "TBD"
                    away = fx["away_team"] or "TBD"
                    hf, af = get_flag(fx.get("home_team")), get_flag(fx.get("away_team"))
                    st.markdown(
                        f"**{hf} {home}** vs **{away} {af}**  \n"
                        f"*{to_cet(fx['kickoff_utc'])} · {fx.get('stadium') or 'TBD'}*"
                    )
                    ph = fx["predicted_home_score"]
                    pa = fx["predicted_away_score"]
                    c1, c2, c3 = st.columns([3, 1, 1])
                    h = c2.number_input(
                        home, min_value=0, max_value=30,
                        value=ph if ph is not None else 0,
                        key=f"h_{fx['match_id']}", disabled=not editable,
                        label_visibility="collapsed",
                    )
                    a = c3.number_input(
                        away, min_value=0, max_value=30,
                        value=pa if pa is not None else 0,
                        key=f"a_{fx['match_id']}", disabled=not editable,
                        label_visibility="collapsed",
                    )
                    inputs[fx["match_id"]] = (int(h), int(a))
                    st.divider()

                submitted = st.form_submit_button(
                    f"Save Group {group} predictions",
                    type="primary", disabled=not editable,
                )

            if submitted and editable:
                items = [
                    {"match_id": mid, "home_score": h, "away_score": a}
                    for mid, (h, a) in inputs.items()
                ]
                try:
                    resp = api_client.submit_predictions(token, "group", items)
                    st.success(f"Saved {resp['saved']} prediction(s) for Group {group}.")
                except Exception:
                    st.error("Couldn't save — the window may have just closed.")

            # Per-group reset
            if editable:
                _reset_expander(token, "group", group, f"Group {group} predictions")


def _render_ko_stage(token: str, stage: str, state: str) -> None:
    editable = state == "open"
    if not editable:
        st.info(f"Predictions are **{STATE_LABELS.get(state, state)}**.")

    data = api_client.get_stage_fixtures(token, stage)
    if not data or not data.get("fixtures"):
        st.warning("No fixtures for this stage yet — they'll appear once the previous round concludes.")
        return

    fixtures = data["fixtures"]

    with st.form(f"preds_{stage}"):
        inputs: dict[str, tuple] = {}
        for fx in fixtures:
            home = fx["home_team"] or "TBD"
            away = fx["away_team"] or "TBD"
            hf, af = get_flag(fx.get("home_team")), get_flag(fx.get("away_team"))
            st.markdown(
                f"**{hf} {home}** vs **{away} {af}**  \n"
                f"*{to_cet(fx['kickoff_utc'])} · {fx.get('stadium') or 'TBD'}*"
            )
            ph, pa = fx["predicted_home_score"], fx["predicted_away_score"]
            c1, c2, c3 = st.columns([3, 1, 1])
            h = c2.number_input(home, min_value=0, max_value=30,
                value=ph if ph is not None else 0,
                key=f"h_{fx['match_id']}", disabled=not editable,
                label_visibility="collapsed")
            a = c3.number_input(away, min_value=0, max_value=30,
                value=pa if pa is not None else 0,
                key=f"a_{fx['match_id']}", disabled=not editable,
                label_visibility="collapsed")
            inputs[fx["match_id"]] = (int(h), int(a))
            st.divider()

        submitted = st.form_submit_button("Save predictions", type="primary", disabled=not editable)

    if submitted and editable:
        items = [{"match_id": mid, "home_score": h, "away_score": a}
                 for mid, (h, a) in inputs.items()]
        try:
            resp = api_client.submit_predictions(token, stage, items)
            st.success(f"Saved {resp['saved']} prediction(s).")
        except Exception:
            st.error("Couldn't save — the window may have just closed.")

    if editable:
        _reset_expander(token, stage, None, f"{stage_label(stage)} predictions")


def render() -> None:
    st.header("🔮 Match predictions")
    token = st.session_state["session_token"]

    windows = api_client.get_windows(token)
    if not windows:
        st.info("Fixtures haven't been loaded yet — nothing to predict right now.")
        return

    selectable = [w for w in windows if w["state"] != "pending"]
    if not selectable:
        st.info("No stages are available for predictions yet.")
        return

    labels = {f"{stage_label(w['stage'])}  ·  {STATE_LABELS[w['state']]}": w for w in selectable}
    default_idx = next((i for i, w in enumerate(selectable) if w["state"] == "open"), 0)
    choice = st.selectbox("Stage", list(labels.keys()), index=default_idx)
    window = labels[choice]
    stage = window["stage"]
    state = window["state"]

    st.divider()

    if stage == "group":
        _render_group_stage(token, state)
    else:
        _render_ko_stage(token, stage, state)
