"""Home view: greeting, next deadline, and per-stage window status."""
from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from frontend import api_client
from frontend.labels import stage_label, STATE_LABELS, to_cet


def render() -> None:
    user = st.session_state["user"]
    st.header(f"Welcome, {user['display_name']}")

    windows = api_client.get_windows(st.session_state["session_token"])
    if not windows:
        st.info("Fixtures haven't been loaded yet. Check back once the schedule is in.")
        return

    # Next deadline = earliest close among currently-open windows.
    now = datetime.now(timezone.utc)
    open_closes = [
        datetime.fromisoformat(w["closes_at"])
        for w in windows
        if w["state"] == "open" and w["closes_at"]
    ]
    if open_closes:
        nxt = min(open_closes)
        delta = nxt - now
        days, hours = delta.days, delta.seconds // 3600
        st.metric("Deadline to submit forecasts:", to_cet(min(open_closes).isoformat()),
                  delta=f"in {days}d {hours}h")
    else:
        st.caption("Prediction window is closed.")

    st.subheader("Stages")
    for w in windows:
        cols = st.columns([2, 2, 3])
        cols[0].write(f"**{stage_label(w['stage'])}**")
        cols[1].write(STATE_LABELS.get(w["state"], w["state"]))
        cols[2].write(f"Closes: {to_cet(w['closes_at'])}")
