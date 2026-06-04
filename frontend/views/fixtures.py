"""Fixtures & Results view: all rounds with SVG flags and knockout placeholders."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from frontend import api_client
from frontend.flags import GROUP_MAP, get_flag_img
from frontend.labels import STAGE_LABELS, to_cet

_CET = ZoneInfo("Europe/Berlin")

ROUND_ORDER = ["group", "r32", "r16", "qf", "sf", "final"]

# Known knockout bracket dates/venues/matchups (all times UTC).
# R32 matchups are fixed by FIFA; R16+ show TBD until R32 resolves.
_KO_PLACEHOLDERS: dict[str, list[dict]] = {
    "r32": [
        {"home": "Runner-up A",  "away": "Runner-up B",  "kickoff": "2026-06-28T19:00:00+00:00", "venue": "SoFi Stadium, Inglewood"},
        {"home": "Winner C",     "away": "Runner-up F",  "kickoff": "2026-06-29T17:00:00+00:00", "venue": "NRG Stadium, Houston"},
        {"home": "Winner E",     "away": "Best 3rd",     "kickoff": "2026-06-29T20:30:00+00:00", "venue": "Gillette Stadium, Foxborough"},
        {"home": "Winner F",     "away": "Runner-up C",  "kickoff": "2026-06-30T01:00:00+00:00", "venue": "Estadio BBVA, Monterrey"},
        {"home": "Runner-up E",  "away": "Runner-up I",  "kickoff": "2026-06-30T17:00:00+00:00", "venue": "AT&T Stadium, Arlington"},
        {"home": "Winner I",     "away": "Best 3rd",     "kickoff": "2026-06-30T21:00:00+00:00", "venue": "MetLife Stadium, East Rutherford"},
        {"home": "Winner A",     "away": "Best 3rd",     "kickoff": "2026-07-01T01:00:00+00:00", "venue": "Estadio Azteca, Mexico City"},
        {"home": "Winner L",     "away": "Best 3rd",     "kickoff": "2026-07-01T16:00:00+00:00", "venue": "Mercedes-Benz Stadium, Atlanta"},
        {"home": "Winner G",     "away": "Best 3rd",     "kickoff": "2026-07-01T20:00:00+00:00", "venue": "Lumen Field, Seattle"},
        {"home": "Winner D",     "away": "Best 3rd",     "kickoff": "2026-07-02T00:00:00+00:00", "venue": "Levi's Stadium, Santa Clara"},
        {"home": "Winner H",     "away": "Runner-up J",  "kickoff": "2026-07-02T19:00:00+00:00", "venue": "SoFi Stadium, Inglewood"},
        {"home": "Runner-up K",  "away": "Runner-up L",  "kickoff": "2026-07-02T23:00:00+00:00", "venue": "BMO Field, Toronto"},
        {"home": "Winner B",     "away": "Best 3rd",     "kickoff": "2026-07-03T03:00:00+00:00", "venue": "BC Place, Vancouver"},
        {"home": "Runner-up D",  "away": "Runner-up G",  "kickoff": "2026-07-03T18:00:00+00:00", "venue": "AT&T Stadium, Arlington"},
        {"home": "Winner J",     "away": "Runner-up H",  "kickoff": "2026-07-03T22:00:00+00:00", "venue": "Hard Rock Stadium, Miami Gardens"},
        {"home": "Winner K",     "away": "Best 3rd",     "kickoff": "2026-07-04T01:30:00+00:00", "venue": "Arrowhead Stadium, Kansas City"},
    ],
    "r16": [
        {"home": "TBD", "away": "TBD", "kickoff": "2026-07-04T17:00:00+00:00", "venue": "NRG Stadium, Houston"},
        {"home": "TBD", "away": "TBD", "kickoff": "2026-07-04T21:00:00+00:00", "venue": "Lincoln Financial Field, Philadelphia"},
        {"home": "TBD", "away": "TBD", "kickoff": "2026-07-05T20:00:00+00:00", "venue": "MetLife Stadium, East Rutherford"},
        {"home": "TBD", "away": "TBD", "kickoff": "2026-07-06T00:00:00+00:00", "venue": "Estadio Azteca, Mexico City"},
        {"home": "TBD", "away": "TBD", "kickoff": "2026-07-06T19:00:00+00:00", "venue": "AT&T Stadium, Arlington"},
        {"home": "TBD", "away": "TBD", "kickoff": "2026-07-07T00:00:00+00:00", "venue": "Lumen Field, Seattle"},
        {"home": "TBD", "away": "TBD", "kickoff": "2026-07-07T16:00:00+00:00", "venue": "Mercedes-Benz Stadium, Atlanta"},
        {"home": "TBD", "away": "TBD", "kickoff": "2026-07-07T20:00:00+00:00", "venue": "BC Place, Vancouver"},
    ],
    "qf": [
        {"home": "TBD", "away": "TBD", "kickoff": "2026-07-09T20:00:00+00:00", "venue": "Gillette Stadium, Foxborough"},
        {"home": "TBD", "away": "TBD", "kickoff": "2026-07-10T19:00:00+00:00", "venue": "SoFi Stadium, Inglewood"},
        {"home": "TBD", "away": "TBD", "kickoff": "2026-07-11T21:00:00+00:00", "venue": "Hard Rock Stadium, Miami Gardens"},
        {"home": "TBD", "away": "TBD", "kickoff": "2026-07-12T01:00:00+00:00", "venue": "Arrowhead Stadium, Kansas City"},
    ],
    "sf": [
        {"home": "TBD", "away": "TBD", "kickoff": "2026-07-14T19:00:00+00:00", "venue": "AT&T Stadium, Arlington"},
        {"home": "TBD", "away": "TBD", "kickoff": "2026-07-15T19:00:00+00:00", "venue": "Mercedes-Benz Stadium, Atlanta"},
    ],
    "final": [
        {"home": "TBD", "away": "TBD", "kickoff": "2026-07-19T19:00:00+00:00", "venue": "MetLife Stadium, East Rutherford"},
    ],
}


def _cet_date_label(iso: str) -> str:
    dt = datetime.fromisoformat(iso).astimezone(_CET)
    return dt.strftime("%A, %d %B")


def _status_badge(fx: dict) -> str:
    if fx.get("home_score") is not None:
        return "🟢 Final"
    return "⏳ Upcoming"


def _match_tile(col, home: str, away: str, kickoff: str, venue: str,
                home_score=None, away_score=None) -> None:
    hfi = get_flag_img(home if home not in ("TBD",) else None)
    afi = get_flag_img(away if away not in ("TBD",) else None)
    scored = home_score is not None
    badge = "🟢 Final" if scored else "⏳ Upcoming"

    with col:
        with st.container(border=True):
            c1, c2, c3 = st.columns([5, 3, 5])
            c1.markdown(f"{hfi}**{home}**", unsafe_allow_html=True)
            if scored:
                c2.markdown(
                    f"<div style='text-align:center;font-size:1.2rem;font-weight:500'>"
                    f"{home_score} – {away_score}</div>",
                    unsafe_allow_html=True,
                )
            else:
                c2.markdown(
                    "<div style='text-align:center;color:var(--color-text-secondary)'>vs</div>",
                    unsafe_allow_html=True,
                )
            c3.markdown(f"**{away}**{afi}", unsafe_allow_html=True)
            st.caption(f"{badge}  ·  {to_cet(kickoff)}  ·  {venue or 'TBD'}")


def _render_group_stage(token: str) -> None:
    data = api_client.get_stage_fixtures(token, "group")
    if not data or not data.get("fixtures"):
        st.info("Group stage fixtures not loaded yet.")
        return

    all_fixtures = data["fixtures"]
    by_group: dict[str, list] = {g: [] for g in "ABCDEFGHIJKL"}
    for fx in all_fixtures:
        grp = (GROUP_MAP.get(fx.get("home_team") or "")
               or GROUP_MAP.get(fx.get("away_team") or ""))
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
                _match_tile(
                    cols[i % 2],
                    fx.get("home_team") or "TBD",
                    fx.get("away_team") or "TBD",
                    fx["kickoff_utc"],
                    fx.get("stadium") or "",
                    fx.get("home_score"),
                    fx.get("away_score"),
                )


def _render_knockout_stage(token: str, stage: str) -> None:
    data = api_client.get_stage_fixtures(token, stage)
    fixtures = (data or {}).get("fixtures", [])

    if not fixtures:
        # Fall back to hardcoded placeholder bracket
        placeholder = _KO_PLACEHOLDERS.get(stage, [])
        if not placeholder:
            st.info("No fixtures available for this stage yet.")
            return
        st.caption("Teams TBD — showing scheduled dates and venues.")
        by_date: dict[str, list] = defaultdict(list)
        for m in placeholder:
            by_date[_cet_date_label(m["kickoff"])].append(m)
        for date_label, matches in by_date.items():
            st.markdown(f"**{date_label}**")
            cols = st.columns(min(len(matches), 2))
            for i, m in enumerate(matches):
                _match_tile(cols[i % 2], m["home"], m["away"],
                            m["kickoff"], m["venue"])
        return

    # Real fixtures (teams known)
    by_date2: dict[str, list] = defaultdict(list)
    for fx in fixtures:
        by_date2[_cet_date_label(fx["kickoff_utc"])].append(fx)
    for date_label, day_fixtures in by_date2.items():
        st.markdown(f"**{date_label}**")
        cols = st.columns(min(len(day_fixtures), 2))
        for i, fx in enumerate(day_fixtures):
            _match_tile(
                cols[i % 2],
                fx.get("home_team") or "TBD",
                fx.get("away_team") or "TBD",
                fx["kickoff_utc"],
                fx.get("stadium") or "",
                fx.get("home_score"),
                fx.get("away_score"),
            )


def render() -> None:
    st.header("📅 Fixtures & Results")
    token = st.session_state["session_token"]

    windows = api_client.get_windows(token)
    present_stages = {w["stage"] for w in windows if w["state"] != "pending"} if windows else set()

    # Always show all rounds as tabs (use placeholders for unseeded knockout stages)
    tab_labels = [STAGE_LABELS.get(s, s) for s in ROUND_ORDER]
    tabs = st.tabs(tab_labels)

    for tab, stage in zip(tabs, ROUND_ORDER):
        with tab:
            if stage == "group":
                if "group" in present_stages:
                    _render_group_stage(token)
                else:
                    st.info("Group stage fixtures not loaded yet.")
            else:
                _render_knockout_stage(token, stage)
