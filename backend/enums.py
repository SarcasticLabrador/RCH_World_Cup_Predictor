"""Domain enumerations shared across models, scoring and scheduling."""
from __future__ import annotations

import enum


class TournamentStatus(str, enum.Enum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    FINISHED = "finished"


class Stage(str, enum.Enum):
    GROUP = "group"
    R32 = "r32"
    R16 = "r16"
    QF = "qf"
    SF = "sf"
    FINAL = "final"


class MatchStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"


class SpecialCategory(str, enum.Enum):
    # Player awards (admin-entered after tournament)
    GOLDEN_BALL = "golden_ball"
    GOLDEN_BOOT = "golden_boot"
    GOLDEN_GLOVE = "golden_glove"
    BEST_YOUNG_PLAYER = "best_young_player"
    # Team award (exact match)
    TEAM_MOST_GOALS = "team_most_goals"
    # Numeric tournament stats (closest wins)
    TOTAL_GOALS = "total_goals"
    YELLOW_CARDS = "yellow_cards"
    RED_CARDS = "red_cards"
    FASTEST_GOAL = "fastest_goal"      # exact minute
    BIGGEST_MARGIN = "biggest_margin"  # goal difference
