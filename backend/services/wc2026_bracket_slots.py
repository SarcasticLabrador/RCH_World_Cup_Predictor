"""Hardcoded 2026 World Cup bracket slot definitions (R32 through Final).

Slot structure is fixed by FIFA before the tournament. Teams and results
are populated later as the tournament progresses.

Match numbers follow the official FIFA schedule (group stage = 1-72,
knockout = 73-104; match 103 is the 3rd-place play-off, excluded here).

All kickoff times are UTC (converted from EDT = UTC-4).

R32 third-place team assignment: each slot lists eligible source groups.
Assignment uses a greedy algorithm processing slots from most-constrained
(fewest eligible qualifying groups) first.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.enums import Stage


@dataclass
class SlotDef:
    match_number: int
    stage: Stage
    home_descriptor: str
    away_descriptor: str
    kickoff_utc: str    # ISO-8601 UTC
    venue: str
    # For R32 "Best 3rd" slots: eligible source groups for the bracket engine.
    home_eligible_groups: list[str] = field(default_factory=list)
    away_eligible_groups: list[str] = field(default_factory=list)
    # For R16+ slots: match numbers whose winners feed into this slot.
    home_from_match: int | None = None
    away_from_match: int | None = None


BRACKET_SLOTS: list[SlotDef] = [
    # ---- Round of 32 ----
    SlotDef(73,  Stage.R32, "Runner-up Group A",  "Runner-up Group B",
            "2026-06-28T19:00:00+00:00", "SoFi Stadium, Inglewood"),
    SlotDef(74,  Stage.R32, "Winner Group E",     "Best 3rd (A/B/C/D/F)",
            "2026-06-29T20:30:00+00:00", "Gillette Stadium, Foxborough",
            away_eligible_groups=["A","B","C","D","F"]),
    SlotDef(75,  Stage.R32, "Winner Group F",     "Runner-up Group C",
            "2026-06-30T01:00:00+00:00", "Estadio BBVA, Monterrey"),
    SlotDef(76,  Stage.R32, "Winner Group C",     "Runner-up Group F",
            "2026-06-29T17:00:00+00:00", "NRG Stadium, Houston"),
    SlotDef(77,  Stage.R32, "Winner Group I",     "Best 3rd (C/D/F/G/H)",
            "2026-06-30T21:00:00+00:00", "MetLife Stadium, East Rutherford",
            away_eligible_groups=["C","D","F","G","H"]),
    SlotDef(78,  Stage.R32, "Runner-up Group E",  "Runner-up Group I",
            "2026-06-30T17:00:00+00:00", "AT&T Stadium, Arlington"),
    SlotDef(79,  Stage.R32, "Winner Group A",     "Best 3rd (C/E/F/H/I)",
            "2026-07-01T01:00:00+00:00", "Estadio Azteca, Mexico City",
            away_eligible_groups=["C","E","F","H","I"]),
    SlotDef(80,  Stage.R32, "Winner Group L",     "Best 3rd (E/H/I/J/K)",
            "2026-07-01T16:00:00+00:00", "Mercedes-Benz Stadium, Atlanta",
            away_eligible_groups=["E","H","I","J","K"]),
    SlotDef(81,  Stage.R32, "Winner Group D",     "Best 3rd (B/E/F/I/J)",
            "2026-07-02T00:00:00+00:00", "Levi's Stadium, Santa Clara",
            away_eligible_groups=["B","E","F","I","J"]),
    SlotDef(82,  Stage.R32, "Winner Group G",     "Best 3rd (A/E/H/I/J)",
            "2026-07-01T20:00:00+00:00", "Lumen Field, Seattle",
            away_eligible_groups=["A","E","H","I","J"]),
    SlotDef(83,  Stage.R32, "Runner-up Group K",  "Runner-up Group L",
            "2026-07-02T23:00:00+00:00", "BMO Field, Toronto"),
    SlotDef(84,  Stage.R32, "Winner Group H",     "Runner-up Group J",
            "2026-07-02T19:00:00+00:00", "SoFi Stadium, Inglewood"),
    SlotDef(85,  Stage.R32, "Winner Group B",     "Best 3rd (E/F/G/I/J)",
            "2026-07-03T03:00:00+00:00", "BC Place, Vancouver",
            away_eligible_groups=["E","F","G","I","J"]),
    SlotDef(86,  Stage.R32, "Winner Group J",     "Runner-up Group H",
            "2026-07-03T22:00:00+00:00", "Hard Rock Stadium, Miami Gardens"),
    SlotDef(87,  Stage.R32, "Winner Group K",     "Best 3rd (D/E/I/J/L)",
            "2026-07-04T01:30:00+00:00", "Arrowhead Stadium, Kansas City",
            away_eligible_groups=["D","E","I","J","L"]),
    SlotDef(88,  Stage.R32, "Runner-up Group D",  "Runner-up Group G",
            "2026-07-03T18:00:00+00:00", "AT&T Stadium, Arlington"),

    # ---- Round of 16 ----
    SlotDef(89,  Stage.R16, "Winner Match 74",    "Winner Match 77",
            "2026-07-04T21:00:00+00:00", "Lincoln Financial Field, Philadelphia",
            home_from_match=74, away_from_match=77),
    SlotDef(90,  Stage.R16, "Winner Match 73",    "Winner Match 75",
            "2026-07-04T17:00:00+00:00", "NRG Stadium, Houston",
            home_from_match=73, away_from_match=75),
    SlotDef(91,  Stage.R16, "Winner Match 76",    "Winner Match 78",
            "2026-07-05T20:00:00+00:00", "MetLife Stadium, East Rutherford",
            home_from_match=76, away_from_match=78),
    SlotDef(92,  Stage.R16, "Winner Match 79",    "Winner Match 80",
            "2026-07-06T00:00:00+00:00", "Estadio Azteca, Mexico City",
            home_from_match=79, away_from_match=80),
    SlotDef(93,  Stage.R16, "Winner Match 83",    "Winner Match 84",
            "2026-07-06T19:00:00+00:00", "AT&T Stadium, Arlington",
            home_from_match=83, away_from_match=84),
    SlotDef(94,  Stage.R16, "Winner Match 81",    "Winner Match 82",
            "2026-07-07T00:00:00+00:00", "Lumen Field, Seattle",
            home_from_match=81, away_from_match=82),
    SlotDef(95,  Stage.R16, "Winner Match 86",    "Winner Match 88",
            "2026-07-07T16:00:00+00:00", "Mercedes-Benz Stadium, Atlanta",
            home_from_match=86, away_from_match=88),
    SlotDef(96,  Stage.R16, "Winner Match 85",    "Winner Match 87",
            "2026-07-07T20:00:00+00:00", "BC Place, Vancouver",
            home_from_match=85, away_from_match=87),

    # ---- Quarter-finals ----
    SlotDef(97,  Stage.QF, "Winner Match 89",    "Winner Match 90",
            "2026-07-09T20:00:00+00:00", "Gillette Stadium, Foxborough",
            home_from_match=89, away_from_match=90),
    SlotDef(98,  Stage.QF, "Winner Match 93",    "Winner Match 94",
            "2026-07-10T19:00:00+00:00", "SoFi Stadium, Inglewood",
            home_from_match=93, away_from_match=94),
    SlotDef(99,  Stage.QF, "Winner Match 91",    "Winner Match 92",
            "2026-07-11T21:00:00+00:00", "Hard Rock Stadium, Miami Gardens",
            home_from_match=91, away_from_match=92),
    SlotDef(100, Stage.QF, "Winner Match 95",    "Winner Match 96",
            "2026-07-12T01:00:00+00:00", "Arrowhead Stadium, Kansas City",
            home_from_match=95, away_from_match=96),

    # ---- Semi-finals ----
    SlotDef(101, Stage.SF, "Winner Match 97",    "Winner Match 98",
            "2026-07-14T19:00:00+00:00", "AT&T Stadium, Arlington",
            home_from_match=97, away_from_match=98),
    SlotDef(102, Stage.SF, "Winner Match 99",    "Winner Match 100",
            "2026-07-15T19:00:00+00:00", "Mercedes-Benz Stadium, Atlanta",
            home_from_match=99, away_from_match=100),

    # ---- Final ----
    SlotDef(104, Stage.FINAL, "Winner Match 101", "Winner Match 102",
            "2026-07-19T19:00:00+00:00", "MetLife Stadium, East Rutherford",
            home_from_match=101, away_from_match=102),
]

# Indexed for fast lookup by match_number.
SLOTS_BY_NUMBER: dict[int, SlotDef] = {s.match_number: s for s in BRACKET_SLOTS}
