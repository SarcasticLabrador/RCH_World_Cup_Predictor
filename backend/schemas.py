"""Pydantic schemas for API requests/responses (shared across routers)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str | None
    is_admin: bool

    model_config = {"from_attributes": True}


class VerifyOut(BaseModel):
    session_token: str
    user: UserOut


class UpdateProfileIn(BaseModel):
    display_name: str


# --- Predictions (Phase 3) ---

class WindowOut(BaseModel):
    stage: str
    opens_at: datetime | None
    closes_at: datetime | None
    state: str  # pending | not_open_yet | open | closed


class FixtureOut(BaseModel):
    match_id: uuid.UUID
    stage: str
    home_team: str | None
    away_team: str | None
    kickoff_utc: datetime
    stadium: str | None
    home_score: int | None
    away_score: int | None
    predicted_home_score: int | None
    predicted_away_score: int | None


class StageFixturesOut(BaseModel):
    stage: str
    state: str
    fixtures: list[FixtureOut]


class PredictionItemIn(BaseModel):
    match_id: uuid.UUID
    home_score: int = Field(ge=0)
    away_score: int = Field(ge=0)


class SubmitPredictionsIn(BaseModel):
    stage: str
    predictions: list[PredictionItemIn]


class SubmitPredictionsOut(BaseModel):
    saved: int


class SeedOut(BaseModel):
    tournament: str
    teams: int
    matches_created: int
    matches_updated: int
    windows: int


# --- Admin: results & scoring (Phase 4) ---

class MatchResultIn(BaseModel):
    match_id: uuid.UUID
    home_score: int = Field(ge=0)
    away_score: int = Field(ge=0)
    finished: bool = True  # set False to revert a match to "not played"


class SpecialResultIn(BaseModel):
    category: str
    actual_value: str


class ScoreSummaryOut(BaseModel):
    match_predictions_scored: int
    special_predictions_scored: int


class TeamStatOut(BaseModel):
    team: str
    goals_for: int
    goals_against: int
    games: int
    goals_for_per_game: float
    goals_against_per_game: float


# --- Specials, teams, leaderboard (Phase 5) ---

class TeamOut(BaseModel):
    name: str
    group: str | None


class SpecialsOut(BaseModel):
    state: str  # open | closed | pending
    categories: list[str]
    predictions: dict[str, str]  # category -> current value


class SpecialItemIn(BaseModel):
    category: str
    value: str


class SubmitSpecialsIn(BaseModel):
    predictions: list[SpecialItemIn]


class SubmitSpecialsOut(BaseModel):
    saved: int


class ResetPasswordIn(BaseModel):
    email: EmailStr
    new_password: str = Field(min_length=8)


class CreateUserIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1, max_length=80)
    is_admin: bool = False


class LeaderboardRowOut(BaseModel):
    rank: int
    user_id: uuid.UUID
    display_name: str
    points: int
    previous_rank: int | None = None


class LeaderboardOut(BaseModel):
    scope: str
    rows: list[LeaderboardRowOut]


# --- AI Match Centre (Phase 7) ---

class FixtureCardOut(BaseModel):
    home: str | None
    away: str | None
    stage: str
    kickoff_utc: str
    stadium: str | None
    home_score: int | None
    away_score: int | None


class MatchCentreOut(BaseModel):
    ai_available: bool
    used_search: bool
    summary: str | None
    recent: list[FixtureCardOut]
    upcoming: list[FixtureCardOut]


# --- AI Match Centre (Phase 7) ---

class FixtureBriefOut(BaseModel):
    home: str
    away: str
    stage: str
    kickoff_utc: datetime
    stadium: str | None
    home_score: int | None
    away_score: int | None


class MatchCentreOut(BaseModel):
    ai_available: bool
    used_search: bool
    summary: str | None
    recent: list[FixtureBriefOut]
    upcoming: list[FixtureBriefOut]
