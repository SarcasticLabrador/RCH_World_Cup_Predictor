"""Display helpers shared by frontend views."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

_CET = ZoneInfo("Europe/Berlin")  # CET / CEST

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

# Special-prediction categories. Auto = derived from match data (override
# still possible); Manual = must be entered by the admin.
SPECIAL_LABELS = {
    "champion": ("Champion", "auto"),
    "runner_up": ("Runner-up", "auto"),
    "most_goals_per_game": ("Most goals scored / game", "auto"),
    "fewest_conceded_per_game": ("Fewest goals conceded / game", "auto"),
    "golden_ball": ("Golden Ball", "manual"),
    "golden_boot": ("Golden Boot", "manual"),
    "golden_glove": ("Golden Glove", "manual"),
    "best_young_player": ("Best Young Player", "manual"),
}


# Which special categories are team picks (dropdown) vs free-text player picks.
TEAM_SPECIALS = {"champion", "runner_up", "most_goals_per_game", "fewest_conceded_per_game"}

# Leaderboard scopes.
SCOPE_LABELS = {
    "overall": "Overall",
    "group": "Group Stage",
    "r32": "Round of 32",
    "r16": "Round of 16",
    "qf": "Quarter-finals",
    "sf": "Semi-finals",
    "final": "Final",
    "specials": "Awards & Specials",
}


def stage_label(stage: str) -> str:
    return STAGE_LABELS.get(stage, stage)


def to_cet(iso_utc: str | None) -> str:
    """Format an ISO-8601 UTC timestamp as local CET/CEST for display."""
    if not iso_utc:
        return "TBD"
    dt = datetime.fromisoformat(iso_utc).astimezone(_CET)
    tzname = dt.tzname() or "CET"
    return dt.strftime(f"%a %d %b %Y, %H:%M ({tzname})")
