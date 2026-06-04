"""Scoring rules for the bracket simulation game.

Group stage (per match):
  Correct tendency (W/D/L)  2 pts
  + Exact scoreline         3 pts extra  (total 5 if exact)

Knockout rounds excl. final (per bracket slot):
  Correct advancing team    2 pts  (position-based: higher predicted score)
  + Exact scoreline         3 pts extra  (penalty score used where applicable)

Final slot:
  Correct champion          25 pts  (position-based winner)
  Correct runner-up         10 pts  (awarded together with champion)
  Exact scoreline           15 pts extra

Individual awards:
  Named categories          10 pts  (exact match)
  Numeric categories        10 pts  (closest wins; ties share)
  Fastest goal              10 pts  (exact minute; falls back to closest)
"""
from __future__ import annotations

from backend.enums import SpecialCategory, Stage

# --- Group stage ---
GROUP_TENDENCY_PTS = 2
GROUP_EXACT_BONUS = 3   # awarded in addition to tendency

# --- Knockout (non-final) ---
KO_WINNER_PTS = 2
KO_EXACT_BONUS = 3

# --- Final ---
FINAL_CHAMPION_PTS = 25
FINAL_RUNNER_UP_PTS = 10   # awarded alongside champion (same pick)
FINAL_EXACT_BONUS = 15

# --- Individual awards ---
AWARD_EXACT_PTS = 10    # named categories and team_most_goals
AWARD_CLOSEST_PTS = 10  # numeric categories (closest prediction wins)

# Numeric categories scored by closest-wins (not exact-only).
NUMERIC_CATEGORIES: set[SpecialCategory] = {
    SpecialCategory.TOTAL_GOALS,
    SpecialCategory.YELLOW_CARDS,
    SpecialCategory.RED_CARDS,
    SpecialCategory.FASTEST_GOAL,   # falls back to closest if no exact
    SpecialCategory.BIGGEST_MARGIN,
}
