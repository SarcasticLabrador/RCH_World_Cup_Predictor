"""Agreed scoring rules, kept as plain constants for easy tweaking.

This module only *declares* the point values. The scoring engine that applies
them is built in Phase 4. Centralising them here means future adjustments
(you mentioned the knockout values may need tweaking) are a one-line change.
"""
from __future__ import annotations

from backend.enums import SpecialCategory, Stage

# --- Match predictions (group + knockout R32..SF) ---
# Per your decision: knockouts use the same group-stage-style scoring to avoid
# point inflation. Exact score and correct-result are NOT additive — exact
# score (the higher tier) supersedes correct-result.
POINTS_EXACT_SCORE = 5
POINTS_CORRECT_RESULT = 2

# Reserved multiplier per stage for future tweaking. All 1.0 today so every
# match round currently scores identically; bump a value to scale a round.
STAGE_MULTIPLIER: dict[Stage, float] = {
    Stage.GROUP: 1.0,
    Stage.R32: 1.0,
    Stage.R16: 1.0,
    Stage.QF: 1.0,
    Stage.SF: 1.0,
    Stage.FINAL: 1.0,  # Final match score handled by FINAL_* below, not this.
}

# --- The Final (independent / additive) ---
# Champion + runner-up are predicted pre-tournament (special predictions).
# The exact final score is its own prediction window opening after the SFs.
POINTS_FINAL_CHAMPION = 25
POINTS_FINAL_RUNNER_UP = 10
POINTS_FINAL_EXACT_SCORE = 15

# --- Special predictions (all submitted pre-tournament) ---
SPECIAL_POINTS: dict[SpecialCategory, int] = {
    SpecialCategory.GOLDEN_BALL: 10,
    SpecialCategory.GOLDEN_BOOT: 10,
    SpecialCategory.GOLDEN_GLOVE: 10,
    SpecialCategory.BEST_YOUNG_PLAYER: 10,
    SpecialCategory.MOST_GOALS_PER_GAME: 10,
    SpecialCategory.FEWEST_CONCEDED_PER_GAME: 10,
    SpecialCategory.CHAMPION: POINTS_FINAL_CHAMPION,
    SpecialCategory.RUNNER_UP: POINTS_FINAL_RUNNER_UP,
}
