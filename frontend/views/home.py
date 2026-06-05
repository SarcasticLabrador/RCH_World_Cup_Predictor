"""Home view: greeting, deadline, scoring rules and prizes."""
from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from frontend import api_client
from frontend.labels import STATE_LABELS, stage_label, to_cet


def _scoring_rules() -> None:
    st.subheader("📋 Scoring rules")

    st.markdown("**Individual matches**")
    st.markdown(
        "**Group stage**\n"
        "- Correct tendency (win / draw / loss): **2 points**\n"
        "- Correct exact scoreline: **+3 points** (total 5 if exact)\n\n"
        "**Knockout rounds**\n"
        "- Correctly predict which team advances: **2 points**\n"
        "- Correct exact scoreline: **+3 points**\n\n"
        "> **Penalty note:** if a match ends 1–1 after extra time and "
        "the shootout ends 4–3, the scoreline to predict is **4–3** "
        "(the penalty result), not 5–4.\n\n"
        "> **Consolation rule:** if you predicted the wrong teams to "
        "come through the group stage but your knockout scoreline still "
        "matches the actual result, you can still earn the 3-point score bonus."
    )

    st.markdown("**Bonus points for the Final**")
    st.markdown(
        "- Correct tournament winner: **25 points**\n"
        "- Correct runner-up: **10 points**\n"
        "- Correct exact scoreline: **+15 points**"
    )

    st.markdown("**Individual awards**")
    st.markdown(
        "- **10 points** for each correct guess\n"
        "- Player and team awards: exact match only\n"
        "- Tournament stats (total goals, cards etc.): "
        "closest guess wins — if nobody guesses exactly right, "
        "the nearest prediction takes the 10 points\n"
        "- Multiple participants can share points "
        "(everyone with the closest / exact answer each gets 10 points)"
    )


def _prizes() -> None:
    st.subheader("🏅 Prizes")
    st.markdown(
        "Each participant can contribute **CHF 10** to the prize pot.\n\n"
        "Send via TWINT to **+41 78 256 50 49**\n\n"
        "| Place | Share |\n"
        "|---|---|\n"
        "| 🥇 Overall winner | 50% of pot |\n"
        "| 🥈 2nd place | 30% of pot |\n"
        "| 🥉 3rd place | 10% of pot |\n"
        "| 🏅 Best individual awards score | 10% of pot |"
    )


def render() -> None:
    user = st.session_state["user"]
    st.header(f"Welcome, {user['display_name']} ⚽")

    token = st.session_state["session_token"]
    dash = api_client.get_dashboard(token) or {}
    windows = dash.get("windows") or api_client.get_windows(token) or []

    if not windows:
        st.info("Fixtures haven't been loaded yet. Check back once the schedule is in.")
    else:
        # Next deadline.
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
            st.metric(
                "Next prediction deadline",
                to_cet(nxt.isoformat()),
                delta=f"in {days}d {hours}h",
            )
        else:
            st.caption("No prediction window is open right now.")

        st.subheader("Stages")
        for w in windows:
            cols = st.columns([2, 2, 3])
            cols[0].write(f"**{stage_label(w['stage'])}**")
            cols[1].write(STATE_LABELS.get(w["state"], w["state"]))
            cols[2].write(f"Closes: {to_cet(w['closes_at'])}")

    st.divider()
    _scoring_rules()
    st.divider()
    _prizes()
