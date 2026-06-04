"""Pydantic schemas for API requests/responses."""
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


# --- Predictions ---

class WindowOut(BaseModel):
    stage: str
    opens_at: datetime | None
    closes_at: datetime | None
    state: str


class FixtureOut(BaseModel):
    match_id: uuid.UUID
    stage: str
    home_team: str | None
    away_team: str | None
    kickoff_utc: datetime
    stadium: str | None
    home_score: int | None
    away_score: int | None
    penalty_home_score: int | None = None
    penalty_away_score: int | None = None
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


class ResetPredictionsIn(BaseModel):
    stage: str
    group: str | None = None


class SeedOut(BaseModel):
    tournament: str
    teams: int
    matches_created: int
    matches_updated: int
    windows: int
    bracket_slots: int = 0


# --- Bracket slots & predictions ---

class BracketSlotOut(BaseModel):
    slot_id: uuid.UUID
    match_number: int
    stage: str
    home_descriptor: str
    away_descriptor: str
    kickoff_utc: datetime
    venue: str | None
    home_team: str | None    # set once teams qualify
    away_team: str | None
    home_score: int | None
    away_score: int | None
    penalty_home_score: int | None = None
    penalty_away_score: int | None = None
    status: str
    # User's prediction for this slot (null if not yet submitted).
    predicted_home_score: int | None = None
    predicted_away_score: int | None = None
    # Derived teams from user's bracket (may differ from confirmed teams).
    derived_home_team: str | None = None
    derived_away_team: str | None = None


class BracketSlotsOut(BaseModel):
    slots: list[BracketSlotOut]


class BracketPredictionItemIn(BaseModel):
    slot_id: uuid.UUID
    home_score: int = Field(ge=0)
    away_score: int = Field(ge=0)


class SubmitBracketPredictionsIn(BaseModel):
    predictions: list[BracketPredictionItemIn]


# --- Admin: results & scoring ---

class MatchResultIn(BaseModel):
    match_id: uuid.UUID
    home_score: int = Field(ge=0)
    away_score: int = Field(ge=0)
    penalty_home_score: int | None = Field(default=None, ge=0)
    penalty_away_score: int | None = Field(default=None, ge=0)
    finished: bool = True


class BracketResultIn(BaseModel):
    match_number: int
    home_score: int = Field(ge=0)
    away_score: int = Field(ge=0)
    penalty_home_score: int | None = Field(default=None, ge=0)
    penalty_away_score: int | None = Field(default=None, ge=0)
    finished: bool = True


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


# --- Specials ---

class TeamOut(BaseModel):
    name: str
    group: str | None


class SpecialsOut(BaseModel):
    state: str
    categories: list[str]
    predictions: dict[str, str]


class SpecialItemIn(BaseModel):
    category: str
    value: str


class SubmitSpecialsIn(BaseModel):
    predictions: list[SpecialItemIn]


class SubmitSpecialsOut(BaseModel):
    saved: int


# --- Admin account management ---

class ResetPasswordIn(BaseModel):
    email: EmailStr
    new_password: str = Field(min_length=8)


class CreateUserIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1, max_length=80)
    is_admin: bool = False


# --- Leaderboard ---

class LeaderboardRowOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    match_pts: int
    award_pts: int
    total_pts: int
    match_pts_rank: int
    award_pts_rank: int
    total_pts_rank: int
    previous_rank: int | None = None


class LeaderboardOut(BaseModel):
    rows: list[LeaderboardRowOut]


# --- AI Match Centre ---

class FixtureBriefOut(BaseModel):
    home: str | None
    away: str | None
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
