"""Display helpers shared by frontend views."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

_CET = ZoneInfo("Europe/Berlin")

STAGE_LABELS = {
    "group": "Group Stage",
    "r32": "Round of 32",
    "r16": "Round of 16",
    "qf": "Quarter-finals",
    "sf": "Semi-finals",
    "final": "Final",
}

STATE_LABELS = {
    "open": "🟢 Open",
    "closed": "🔒 Closed",
    "not_open_yet": "⏳ Not open yet",
    "pending": "… Awaiting fixtures",
}

SPECIAL_LABELS: dict[str, tuple[str, str]] = {
    # (display_name, input_type: "player" | "team" | "number")
    "golden_ball":       ("Golden Ball",               "player"),
    "golden_boot":       ("Golden Boot",               "player"),
    "golden_glove":      ("Golden Glove",              "player"),
    "best_young_player": ("Best Young Player",         "player"),
    "team_most_goals":   ("Team — most goals scored",  "team"),
    "total_goals":       ("Total goals in tournament", "number"),
    "yellow_cards":      ("Yellow cards",              "number"),
    "red_cards":         ("Red cards",                 "number"),
    "fastest_goal":      ("Fastest goal (minute)",     "number"),
    "biggest_margin":    ("Biggest winning margin",    "number"),
}

SPECIAL_ORDER = list(SPECIAL_LABELS.keys())

# Leaderboard sort options.
LEADERBOARD_VIEWS = {
    "total_pts":  "Overall",
    "match_pts":  "Match predictions",
    "award_pts":  "Individual awards",
}


def stage_label(stage: str) -> str:
    return STAGE_LABELS.get(stage, stage)


def to_cet(iso_utc: str | datetime | None) -> str:
    if not iso_utc:
        return "TBD"
    if isinstance(iso_utc, str):
        iso_utc = datetime.fromisoformat(iso_utc)
    dt = iso_utc.astimezone(_CET)
    tzname = dt.tzname() or "CET"
    return dt.strftime(f"%a %d %b %Y, %H:%M ({tzname})")
