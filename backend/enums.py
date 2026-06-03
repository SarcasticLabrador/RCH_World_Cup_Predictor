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
    GOLDEN_BALL = "golden_ball"
    GOLDEN_BOOT = "golden_boot"
    GOLDEN_GLOVE = "golden_glove"
    BEST_YOUNG_PLAYER = "best_young_player"
    MOST_GOALS_PER_GAME = "most_goals_per_game"
    FEWEST_CONCEDED_PER_GAME = "fewest_conceded_per_game"
    CHAMPION = "champion"
    RUNNER_UP = "runner_up"
