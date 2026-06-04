"""Hardcoded 2026 FIFA World Cup group stage fixtures.

All 72 group stage matches, converted from Eastern Time (EDT, UTC-4) to UTC.
Used as a fallback when the API-Football key is unavailable.
"""
from __future__ import annotations

from datetime import datetime, timezone

from backend.enums import MatchStatus, Stage
from backend.services.football_api import NormalizedMatch


def _nm(ext_id: str, group: str, home: str, away: str, kickoff: str, venue: str) -> NormalizedMatch:
    return NormalizedMatch(
        external_id=ext_id,
        stage=Stage.GROUP,
        kickoff_utc=datetime.fromisoformat(kickoff),
        stadium=venue,
        home_external_id=home.lower().replace(" ", "_").replace("ü", "u").replace("ç", "c").replace("é", "e").replace("ô", "o"),
        home_name=home,
        away_external_id=away.lower().replace(" ", "_").replace("ü", "u").replace("ç", "c").replace("é", "e").replace("ô", "o"),
        away_name=away,
        home_score=None,
        away_score=None,
        status=MatchStatus.SCHEDULED,
    )


# All kickoff times in UTC (converted from EDT = UTC-4)
_FIXTURES_RAW = [
    # ---- June 11 ----
    ("1",  "A", "Mexico",               "South Africa",      "2026-06-11T19:00:00+00:00", "Estadio Azteca, Mexico City"),
    ("2",  "A", "South Korea",          "Czechia",           "2026-06-12T02:00:00+00:00", "Estadio Akron, Zapopan"),
    # ---- June 12 ----
    ("3",  "B", "Canada",               "Bosnia & Herzegovina", "2026-06-12T19:00:00+00:00", "BMO Field, Toronto"),
    ("4",  "D", "USA",                  "Paraguay",          "2026-06-13T01:00:00+00:00", "SoFi Stadium, Inglewood"),
    # ---- June 13 ----
    ("5",  "B", "Qatar",                "Switzerland",       "2026-06-13T19:00:00+00:00", "Levi's Stadium, Santa Clara"),
    ("6",  "C", "Brazil",               "Morocco",           "2026-06-13T22:00:00+00:00", "MetLife Stadium, East Rutherford"),
    ("7",  "C", "Haiti",                "Scotland",          "2026-06-14T01:00:00+00:00", "Gillette Stadium, Foxborough"),
    # ---- June 14 ----
    ("8",  "D", "Australia",            "Turkiye",           "2026-06-14T04:00:00+00:00", "BC Place, Vancouver"),
    ("9",  "E", "Germany",              "Curacao",           "2026-06-14T17:00:00+00:00", "NRG Stadium, Houston"),
    ("10", "F", "Netherlands",          "Japan",             "2026-06-14T20:00:00+00:00", "AT&T Stadium, Arlington"),
    ("11", "E", "Ivory Coast",          "Ecuador",           "2026-06-14T23:00:00+00:00", "Lincoln Financial Field, Philadelphia"),
    ("12", "F", "Sweden",               "Tunisia",           "2026-06-15T02:00:00+00:00", "Estadio BBVA, Monterrey"),
    # ---- June 15 ----
    ("13", "H", "Spain",                "Cape Verde",        "2026-06-15T16:00:00+00:00", "Mercedes-Benz Stadium, Atlanta"),
    ("14", "G", "Belgium",              "Egypt",             "2026-06-15T19:00:00+00:00", "Lumen Field, Seattle"),
    ("15", "H", "Saudi Arabia",         "Uruguay",           "2026-06-15T22:00:00+00:00", "Hard Rock Stadium, Miami Gardens"),
    ("16", "G", "Iran",                 "New Zealand",       "2026-06-16T01:00:00+00:00", "SoFi Stadium, Inglewood"),
    # ---- June 16 ----
    ("17", "I", "France",               "Senegal",           "2026-06-16T19:00:00+00:00", "MetLife Stadium, East Rutherford"),
    ("18", "I", "Iraq",                 "Norway",            "2026-06-16T22:00:00+00:00", "Gillette Stadium, Foxborough"),
    ("19", "J", "Argentina",            "Algeria",           "2026-06-17T01:00:00+00:00", "Arrowhead Stadium, Kansas City"),
    # ---- June 17 ----
    ("20", "J", "Austria",              "Jordan",            "2026-06-17T04:00:00+00:00", "Levi's Stadium, Santa Clara"),
    ("21", "K", "Portugal",             "DR Congo",          "2026-06-17T17:00:00+00:00", "NRG Stadium, Houston"),
    ("22", "L", "England",              "Croatia",           "2026-06-17T20:00:00+00:00", "AT&T Stadium, Arlington"),
    ("23", "L", "Ghana",                "Panama",            "2026-06-17T23:00:00+00:00", "BMO Field, Toronto"),
    ("24", "K", "Uzbekistan",           "Colombia",          "2026-06-18T02:00:00+00:00", "Estadio Azteca, Mexico City"),
    # ---- June 18 ----
    ("25", "A", "Czechia",              "South Africa",      "2026-06-18T16:00:00+00:00", "Mercedes-Benz Stadium, Atlanta"),
    ("26", "B", "Switzerland",          "Bosnia & Herzegovina", "2026-06-18T19:00:00+00:00", "SoFi Stadium, Inglewood"),
    ("27", "B", "Canada",               "Qatar",             "2026-06-18T22:00:00+00:00", "BC Place, Vancouver"),
    ("28", "A", "Mexico",               "South Korea",       "2026-06-19T01:00:00+00:00", "Estadio Akron, Zapopan"),
    # ---- June 19 ----
    ("29", "D", "USA",                  "Australia",         "2026-06-19T19:00:00+00:00", "Lumen Field, Seattle"),
    ("30", "C", "Scotland",             "Morocco",           "2026-06-19T22:00:00+00:00", "Gillette Stadium, Foxborough"),
    ("31", "C", "Brazil",               "Haiti",             "2026-06-20T00:30:00+00:00", "Lincoln Financial Field, Philadelphia"),
    ("32", "D", "Turkiye",              "Paraguay",          "2026-06-20T03:00:00+00:00", "Levi's Stadium, Santa Clara"),
    # ---- June 20 ----
    ("33", "F", "Netherlands",          "Sweden",            "2026-06-20T17:00:00+00:00", "NRG Stadium, Houston"),
    ("34", "E", "Germany",              "Ivory Coast",       "2026-06-20T20:00:00+00:00", "BMO Field, Toronto"),
    ("35", "E", "Ecuador",              "Curacao",           "2026-06-21T00:00:00+00:00", "Arrowhead Stadium, Kansas City"),
    # ---- June 21 ----
    ("36", "F", "Tunisia",              "Japan",             "2026-06-21T04:00:00+00:00", "Estadio BBVA, Monterrey"),
    ("37", "H", "Spain",                "Saudi Arabia",      "2026-06-21T16:00:00+00:00", "Mercedes-Benz Stadium, Atlanta"),
    ("38", "G", "Belgium",              "Iran",              "2026-06-21T19:00:00+00:00", "SoFi Stadium, Inglewood"),
    ("39", "H", "Uruguay",              "Cape Verde",        "2026-06-21T22:00:00+00:00", "Hard Rock Stadium, Miami Gardens"),
    ("40", "G", "New Zealand",          "Egypt",             "2026-06-22T01:00:00+00:00", "BC Place, Vancouver"),
    # ---- June 22 ----
    ("41", "J", "Argentina",            "Austria",           "2026-06-22T17:00:00+00:00", "AT&T Stadium, Arlington"),
    ("42", "I", "France",               "Iraq",              "2026-06-22T21:00:00+00:00", "Lincoln Financial Field, Philadelphia"),
    ("43", "I", "Norway",               "Senegal",           "2026-06-23T00:00:00+00:00", "MetLife Stadium, East Rutherford"),
    ("44", "J", "Jordan",               "Algeria",           "2026-06-23T03:00:00+00:00", "Levi's Stadium, Santa Clara"),
    # ---- June 23 ----
    ("45", "K", "Portugal",             "Uzbekistan",        "2026-06-23T17:00:00+00:00", "NRG Stadium, Houston"),
    ("46", "L", "England",              "Ghana",             "2026-06-23T20:00:00+00:00", "Gillette Stadium, Foxborough"),
    ("47", "L", "Panama",               "Croatia",           "2026-06-23T23:00:00+00:00", "BMO Field, Toronto"),
    ("48", "K", "Colombia",             "DR Congo",          "2026-06-24T02:00:00+00:00", "Estadio Akron, Zapopan"),
    # ---- June 24 (simultaneous) ----
    ("49", "B", "Switzerland",          "Canada",            "2026-06-24T19:00:00+00:00", "BC Place, Vancouver"),
    ("50", "B", "Bosnia & Herzegovina", "Qatar",             "2026-06-24T19:00:00+00:00", "Lumen Field, Seattle"),
    ("51", "C", "Scotland",             "Brazil",            "2026-06-24T22:00:00+00:00", "Hard Rock Stadium, Miami Gardens"),
    ("52", "C", "Morocco",              "Haiti",             "2026-06-24T22:00:00+00:00", "Mercedes-Benz Stadium, Atlanta"),
    ("53", "A", "Czechia",              "Mexico",            "2026-06-25T01:00:00+00:00", "Estadio Azteca, Mexico City"),
    ("54", "A", "South Africa",         "South Korea",       "2026-06-25T01:00:00+00:00", "Estadio BBVA, Monterrey"),
    # ---- June 25 (simultaneous) ----
    ("55", "E", "Curacao",              "Ivory Coast",       "2026-06-25T20:00:00+00:00", "Lincoln Financial Field, Philadelphia"),
    ("56", "E", "Ecuador",              "Germany",           "2026-06-25T20:00:00+00:00", "MetLife Stadium, East Rutherford"),
    ("57", "F", "Japan",                "Sweden",            "2026-06-25T23:00:00+00:00", "AT&T Stadium, Arlington"),
    ("58", "F", "Tunisia",              "Netherlands",       "2026-06-25T23:00:00+00:00", "Arrowhead Stadium, Kansas City"),
    ("59", "D", "Turkiye",              "USA",               "2026-06-26T02:00:00+00:00", "SoFi Stadium, Inglewood"),
    ("60", "D", "Paraguay",             "Australia",         "2026-06-26T02:00:00+00:00", "Levi's Stadium, Santa Clara"),
    # ---- June 26 (simultaneous) ----
    ("61", "I", "Norway",               "France",            "2026-06-26T19:00:00+00:00", "Gillette Stadium, Foxborough"),
    ("62", "I", "Senegal",              "Iraq",              "2026-06-26T19:00:00+00:00", "BMO Field, Toronto"),
    ("63", "H", "Cape Verde",           "Saudi Arabia",      "2026-06-27T00:00:00+00:00", "NRG Stadium, Houston"),
    ("64", "H", "Uruguay",              "Spain",             "2026-06-27T00:00:00+00:00", "Estadio Akron, Zapopan"),
    ("65", "G", "Egypt",                "Iran",              "2026-06-27T03:00:00+00:00", "Lumen Field, Seattle"),
    ("66", "G", "New Zealand",          "Belgium",           "2026-06-27T03:00:00+00:00", "BC Place, Vancouver"),
    # ---- June 27 (simultaneous) ----
    ("67", "L", "Panama",               "England",           "2026-06-27T21:00:00+00:00", "MetLife Stadium, East Rutherford"),
    ("68", "L", "Croatia",              "Ghana",             "2026-06-27T21:00:00+00:00", "Lincoln Financial Field, Philadelphia"),
    ("69", "K", "Colombia",             "Portugal",          "2026-06-27T23:30:00+00:00", "Hard Rock Stadium, Miami Gardens"),
    ("70", "K", "DR Congo",             "Uzbekistan",        "2026-06-27T23:30:00+00:00", "Mercedes-Benz Stadium, Atlanta"),
    ("71", "J", "Algeria",              "Austria",           "2026-06-28T02:00:00+00:00", "Arrowhead Stadium, Kansas City"),
    ("72", "J", "Jordan",               "Argentina",         "2026-06-28T02:00:00+00:00", "AT&T Stadium, Arlington"),
]


def get_2026_fixtures() -> list[NormalizedMatch]:
    return [_nm(*row) for row in _FIXTURES_RAW]


def get_2026_groups() -> dict[str, str]:
    """Map team external_id -> group letter."""
    groups = {}
    for _, group, home, away, _, _ in _FIXTURES_RAW:
        for name in (home, away):
            ext_id = name.lower().replace(" ", "_").replace("ü", "u").replace("ç", "c").replace("é", "e").replace("ô", "o")
            groups[ext_id] = group
    return groups
