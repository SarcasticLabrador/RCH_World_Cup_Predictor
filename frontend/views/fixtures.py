"""Fixtures & Results view: all rounds, match tiles with flags and scores."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from frontend import api_client
from frontend.flags import GROUP_MAP, get_flag
from frontend.labels import STAGE_LABELS, STATE_LABELS, to_cet

_CET = ZoneInfo("Europe/Berlin")

ROUND_ORDER = ["group", "r32", "r16", "qf", "sf", "final"]


def _cet_date_label(iso: str) -> str:
    dt = datetime.fromisoformat(iso).astimezone(_CET)
    return dt.strftime("%A, %d %B")


def _status_badge(fx: dict) -> str:
    if fx.get("home_score") is not None:
        return "🟢 Final"
    return "⏳ Upcoming"


def _match_tile(col, fx: dict) -> None:
    home = fx.get("home_team") or "TBD"
    away = fx.get("away_team") or "TBD"
    hf, af = get_flag(fx.get("home_team")), get_flag(fx.get("away_team"))
    scored = fx.get("home_score") is not None

    with col:
        with st.container(border=True):
            c1, c2, c3 = st.columns([5, 3, 5])
            c1.markdown(f"{hf} **{home}**")
            if scored:
                c2.markdown(
                    f"<div style='text-align:center;font-size:1.2rem;font-weight:500'>"
                    f"{fx['home_score']} – {fx['away_score']}</div>",
                    unsafe_allow_html=True,
                )
            else:
                c2.markdown(
                    "<div style='text-align:center;color:var(--color-text-secondary)'>vs</div>",
                    unsafe_allow_html=True,
                )
            c3.markdown(f"**{away}** {af}")
            st.caption(f"{_status_badge(fx)}  ·  {to_cet(fx['kickoff_utc'])}  ·  {fx.get('stadium') or 'TBD'}")


def _render_group_stage(token: str) -> None:
    data = api_client.get_stage_fixtures(token, "group")
    if not data or not data.get("fixtures"):
        st.info("Group stage fixtures not loaded yet.")
        return

    all_fixtures = data["fixtures"]
    by_group: dict[str, list] = {g: [] for g in "ABCDEFGHIJKL"}
    for fx in all_fixtures:
        grp = GROUP_MAP.get(fx.get("home_team") or "") or GROUP_MAP.get(fx.get("away_team") or "")
        if grp:
            by_group[grp].append(fx)

    tabs = st.tabs([f"Group {g}" for g in "ABCDEFGHIJKL"])
    for tab, group in zip(tabs, "ABCDEFGHIJKL"):
        with tab:
            fixtures = sorted(by_group[group], key=lambda f: f["kickoff_utc"])
            if not fixtures:
                st.caption("No fixtures for this group yet.")
                continue
            cols = st.columns(2)
            for i, fx in enumerate(fixtures):
                _match_tile(cols[i % 2], fx)


def _render_knockout_stage(token: str, stage: str) -> None:
    data = api_client.get_stage_fixtures(token, stage)
    if not data or not data.get("fixtures"):
        st.info("Fixtures for this round haven't been seeded yet — they'll appear once the previous round concludes.")
        return

    fixtures = data["fixtures"]
    by_date: dict[str, list] = defaultdict(list)
    for fx in fixtures:
        by_date[_cet_date_label(fx["kickoff_utc"])].append(fx)

    for date_label, day_fixtures in by_date.items():
        st.markdown(f"**{date_label}**")
        cols = st.columns(min(len(day_fixtures), 2))
        for i, fx in enumerate(day_fixtures):
            _match_tile(cols[i % 2], fx)
        st.divider()


def render() -> None:
    st.header("📅 Fixtures & Results")
    token = st.session_state["session_token"]

    windows = api_client.get_windows(token)
    if not windows:
        st.info("Fixtures haven't been loaded yet.")
        return

    present_stages = {w["stage"] for w in windows if w["state"] != "pending"}
    tab_stages = [s for s in ROUND_ORDER if s in present_stages]

    if not tab_stages:
        st.info("No fixtures available yet.")
        return

    tab_labels = [STAGE_LABELS.get(s, s) for s in tab_stages]
    tabs = st.tabs(tab_labels)

    for tab, stage in zip(tabs, tab_stages):
        with tab:
            if stage == "group":
                _render_group_stage(token)
            else:
                _render_knockout_stage(token, stage)
