"""Match predictions view: group stage with live standings + bracket view."""
from __future__ import annotations

from collections import defaultdict

import streamlit as st

from frontend import api_client
from frontend.flags import GROUP_MAP, get_flag_img
from frontend.labels import STAGE_LABELS, STATE_LABELS, stage_label, to_cet

GROUPS = list("ABCDEFGHIJKL")


# ── Reset helper ─────────────────────────────────────────────────────────────

def _reset_expander(token: str, stage: str, group: str | None, label: str) -> None:
    key = f"{stage}_{group or 'all'}"
    with st.expander(f"⚠️ Reset {label}"):
        st.warning("This permanently clears the selected predictions and cannot be undone.")
        if st.checkbox("I understand", key=f"confirm_{key}"):
            if st.button("Reset", key=f"do_reset_{key}"):
                try:
                    api_client.reset_predictions(token, stage, group)
                    api_client.get_stage_fixtures.clear()
                    api_client.get_bracket_slots.clear()
                    st.success("Predictions cleared.")
                    st.rerun()
                except Exception as e:
                    if "409" in str(e):
                        st.error("Window is locked — no changes possible.")
                    else:
                        st.error("Reset failed — please try again.")


# ── Standings helper ──────────────────────────────────────────────────────────

def _render_standings_table(fixtures: list[dict], group: str) -> None:
    """Compute and render a mini standings table from saved predictions."""
    group_fx = [f for f in fixtures if GROUP_MAP.get(f.get("home_team") or "") == group
                or GROUP_MAP.get(f.get("away_team") or "") == group]

    teams: dict[str, dict] = {}
    for fx in group_fx:
        for name in (fx.get("home_team"), fx.get("away_team")):
            if name and name not in teams:
                teams[name] = {"P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "Pts": 0}

    for fx in group_fx:
        ph, pa = fx.get("predicted_home_score"), fx.get("predicted_away_score")
        h, a = fx.get("home_team"), fx.get("away_team")
        if ph is None or pa is None or not h or not a:
            continue
        teams[h]["P"] += 1; teams[a]["P"] += 1
        teams[h]["GF"] += ph; teams[h]["GA"] += pa
        teams[a]["GF"] += pa; teams[a]["GA"] += ph
        if ph > pa:
            teams[h]["W"] += 1; teams[h]["Pts"] += 3; teams[a]["L"] += 1
        elif pa > ph:
            teams[a]["W"] += 1; teams[a]["Pts"] += 3; teams[h]["L"] += 1
        else:
            teams[h]["D"] += 1; teams[h]["Pts"] += 1
            teams[a]["D"] += 1; teams[a]["Pts"] += 1

    if not any(t["P"] > 0 for t in teams.values()):
        return

    rows = sorted(
        teams.items(),
        key=lambda kv: (-kv[1]["Pts"], -(kv[1]["GF"] - kv[1]["GA"]), -kv[1]["GF"], kv[0].lower()),
    )
    table = [
        {
            "": n,
            "P": r["P"], "W": r["W"], "D": r["D"], "L": r["L"],
            "GF": r["GF"], "GA": r["GA"], "GD": r["GF"] - r["GA"], "Pts": r["Pts"],
        }
        for n, r in rows
    ]
    st.caption("Predicted standings (based on saved predictions)")
    st.dataframe(table, use_container_width=True, hide_index=True)


# ── Group stage predictions ───────────────────────────────────────────────────

def _render_group_stage(token: str, state: str) -> None:
    editable = state == "open"
    if not editable:
        st.info(f"Group stage predictions are **{STATE_LABELS.get(state, state)}**.")

    data = api_client.get_stage_fixtures(token, "group")
    if not data or not data.get("fixtures"):
        st.info("No group stage fixtures loaded yet.")
        return

    all_fixtures = data["fixtures"]

    if editable:
        _reset_expander(token, "group", None, "ALL group stage predictions")
        st.divider()

    tabs = st.tabs([f"Group {g}" for g in GROUPS])
    for tab, group in zip(tabs, GROUPS):
        with tab:
            fixtures = sorted(
                [f for f in all_fixtures
                 if GROUP_MAP.get(f.get("home_team") or "") == group
                 or GROUP_MAP.get(f.get("away_team") or "") == group],
                key=lambda f: f["kickoff_utc"],
            )
            if not fixtures:
                st.caption("No fixtures for this group yet.")
                continue

            with st.form(f"preds_group_{group}"):
                inputs: dict = {}
                for fx in fixtures:
                    home = fx["home_team"] or "TBD"
                    away = fx["away_team"] or "TBD"
                    hfi = get_flag_img(fx.get("home_team"))
                    afi = get_flag_img(fx.get("away_team"))
                    st.markdown(
                        f"{hfi}**{home}** vs **{away}**{afi}  \n"
                        f"*{to_cet(fx['kickoff_utc'])} · {fx.get('stadium') or 'TBD'}*",
                        unsafe_allow_html=True,
                    )
                    ph, pa = fx["predicted_home_score"], fx["predicted_away_score"]
                    c1, c2, c3 = st.columns([3, 1, 1])
                    h_val = c2.number_input(home, min_value=0, max_value=30,
                        value=ph if ph is not None else 0,
                        key=f"h_{fx['match_id']}", disabled=not editable,
                        label_visibility="collapsed")
                    a_val = c3.number_input(away, min_value=0, max_value=30,
                        value=pa if pa is not None else 0,
                        key=f"a_{fx['match_id']}", disabled=not editable,
                        label_visibility="collapsed")
                    inputs[fx["match_id"]] = (int(h_val), int(a_val))
                    st.divider()

                submitted = st.form_submit_button(
                    f"Save Group {group} predictions", type="primary", disabled=not editable
                )

            if submitted and editable:
                items = [{"match_id": mid, "home_score": h, "away_score": a}
                         for mid, (h, a) in inputs.items()]
                try:
                    resp = api_client.submit_predictions(token, "group", items)
                    api_client.get_stage_fixtures.clear()   # fresh fixtures on rerun
                    api_client.get_bracket_slots.clear()     # bracket derives from group preds
                    st.success(f"Saved {resp['saved']} prediction(s).")
                    st.rerun()
                except Exception:
                    st.error("Couldn't save — the window may have just closed.")

            # Standings from saved predictions
            _render_standings_table(all_fixtures, group)

            if editable:
                _reset_expander(token, "group", group, f"Group {group} predictions")


# ── Bracket predictions ───────────────────────────────────────────────────────

_BRACKET_STAGE_ORDER = ["r32", "r16", "qf", "sf", "final"]
_BRACKET_STAGE_LABELS = {
    "r32": "Round of 32", "r16": "Round of 16",
    "qf": "Quarter-finals", "sf": "Semi-finals", "final": "Final",
}


def _render_bracket(token: str) -> None:
    data = api_client.get_bracket_slots(token)
    if not data or not data.get("slots"):
        st.info("Bracket slots haven't been seeded yet. Run the manual seed endpoint first.")
        return

    slots = data["slots"]
    by_stage: dict[str, list] = defaultdict(list)
    for s in slots:
        by_stage[s["stage"]].append(s)

    stages_present = [s for s in _BRACKET_STAGE_ORDER if s in by_stage]
    if not stages_present:
        st.info("No bracket slots found.")
        return

    tabs = st.tabs([_BRACKET_STAGE_LABELS[s] for s in stages_present])
    for tab, stage in zip(tabs, stages_present):
        with tab:
            stage_slots = sorted(by_stage[stage], key=lambda s: s["match_number"])
            _render_bracket_stage(token, stage, stage_slots)


def _render_bracket_stage(token: str, stage: str, slots: list[dict]) -> None:
    with st.form(f"bracket_{stage}"):
        inputs: dict = {}
        for sl in slots:
            # Use confirmed teams if known; fall back to derived; then descriptor.
            home = sl.get("home_team") or sl.get("derived_home_team") or sl["home_descriptor"]
            away = sl.get("away_team") or sl.get("derived_away_team") or sl["away_descriptor"]
            hfi = get_flag_img(sl.get("home_team") or sl.get("derived_home_team"))
            afi = get_flag_img(sl.get("away_team") or sl.get("derived_away_team"))
            is_tbd = not (sl.get("home_team") or sl.get("derived_home_team"))

            st.markdown(
                f"**Match {sl['match_number']}** · {to_cet(sl['kickoff_utc'])}  \n"
                f"{hfi}**{home}** vs **{away}**{afi}",
                unsafe_allow_html=True,
            )
            if is_tbd:
                st.caption("⏳ Predict your group stage first to see the derived teams.")

            ph = sl.get("predicted_home_score")
            pa = sl.get("predicted_away_score")
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.caption(sl["venue"] or "")
            h_val = c2.number_input(home, min_value=0, max_value=30,
                value=ph if ph is not None else 0,
                key=f"bh_{sl['slot_id']}", label_visibility="collapsed")
            a_val = c3.number_input(away, min_value=0, max_value=30,
                value=pa if pa is not None else 0,
                key=f"ba_{sl['slot_id']}", label_visibility="collapsed")
            inputs[sl["slot_id"]] = (int(h_val), int(a_val))
            st.divider()

        submitted = st.form_submit_button(
            f"Save {_BRACKET_STAGE_LABELS[stage]} predictions", type="primary"
        )

    if submitted:
        items = [{"slot_id": sid, "home_score": h, "away_score": a}
                 for sid, (h, a) in inputs.items()]
        try:
            resp = api_client.submit_bracket_predictions(token, items)
            api_client.get_bracket_slots.clear()  # force fresh fetch on rerun
            st.success(f"Saved {resp['saved']} prediction(s).")
            st.rerun()
        except Exception:
            st.error("Couldn't save. Please try again.")


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    st.header("🔮 Match predictions")
    token = st.session_state["session_token"]

    windows = api_client.get_windows(token)
    if not windows:
        st.info("Fixtures haven't been loaded yet.")
        return

    group_window = next((w for w in windows if w["stage"] == "group"), None)
    group_state = group_window["state"] if group_window else "pending"

    group_tab, bracket_tab = st.tabs(["Group Stage", "Bracket & Knockouts"])

    with group_tab:
        _render_group_stage(token, group_state)

    with bracket_tab:
        _render_bracket(token)
