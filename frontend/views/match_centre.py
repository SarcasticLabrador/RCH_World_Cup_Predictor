"""AI Match Centre: daily summary plus recent results and upcoming fixtures."""
from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.labels import stage_label, to_cet


def _fixture_line(fx: dict, played: bool) -> str:
    when = to_cet(fx["kickoff_utc"])
    venue = f" · {fx['stadium']}" if fx.get("stadium") else ""
    if played:
        return f"**{fx['home']} {fx['home_score']}–{fx['away_score']} {fx['away']}**  \n*{stage_label(fx['stage'])} · {when}*"
    return f"**{fx['home']} vs {fx['away']}**  \n*{stage_label(fx['stage'])}{venue} · {when}*"


def render() -> None:
    st.header("🤖 AI Match Centre")
    token = st.session_state["session_token"]

    c1, c2 = st.columns([3, 1])
    news = c1.toggle("Include latest team news", value=False, help="Uses Google Search grounding")
    refresh = c2.button("Refresh")

    data = api_client.get_match_centre(token, news=news, refresh=refresh)
    if data is None:
        st.info("Fixtures haven't been loaded yet.")
        return

    if data.get("summary"):
        st.markdown(data["summary"])
        if data.get("used_search"):
            st.caption("Includes web-sourced team news — details may change.")
    elif not data["ai_available"]:
        st.info("Add a Gemini API key on the server to enable AI summaries. Fixtures are shown below.")
    else:
        st.warning("AI summary is temporarily unavailable. Fixtures are shown below.")

    st.divider()
    col_recent, col_upcoming = st.columns(2)
    with col_recent:
        st.subheader("Recent results")
        if data["recent"]:
            for fx in data["recent"]:
                st.markdown(_fixture_line(fx, True))
        else:
            st.caption("No recent matches.")
    with col_upcoming:
        st.subheader("Upcoming")
        if data["upcoming"]:
            for fx in data["upcoming"]:
                st.markdown(_fixture_line(fx, False))
        else:
            st.caption("No upcoming matches in the next couple of days.")
