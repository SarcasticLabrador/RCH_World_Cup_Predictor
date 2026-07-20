"""SQLAlchemy ORM models for the World Cup Predictor."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.db.types import GUID, new_uuid
from backend.enums import MatchStatus, SpecialCategory, Stage, TournamentStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enum(py_enum):
    return SAEnum(py_enum, native_enum=False, validate_strings=True, length=32)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(80))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(128))
    # Manual score overrides — when set, replace the computed values on the
    # leaderboard. Null = use computed score (the default for everyone).
    manual_match_points: Mapped[int | None] = mapped_column(Integer)
    manual_award_points: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    magic_links: Mapped[list["MagicLink"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    predictions: Mapped[list["Prediction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    bracket_predictions: Mapped[list["BracketPrediction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    special_predictions: Mapped[list["SpecialPrediction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class MagicLink(Base):
    __tablename__ = "magic_links"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="magic_links")


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[TournamentStatus] = mapped_column(
        _enum(TournamentStatus), default=TournamentStatus.UPCOMING, nullable=False
    )
    predictions_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    teams: Mapped[list["Team"]] = relationship(
        back_populates="tournament", cascade="all, delete-orphan"
    )
    matches: Mapped[list["Match"]] = relationship(
        back_populates="tournament", cascade="all, delete-orphan"
    )
    bracket_slots: Mapped[list["BracketSlot"]] = relationship(
        back_populates="tournament", cascade="all, delete-orphan"
    )


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    tournament_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    group: Mapped[str | None] = mapped_column(String(2))
    flag_url: Mapped[str | None] = mapped_column(String(255))
    external_id: Mapped[str | None] = mapped_column(String(40), index=True)

    tournament: Mapped["Tournament"] = relationship(back_populates="teams")

    __table_args__ = (UniqueConstraint("tournament_id", "name", name="uq_team_per_tournament"),)


class Match(Base):
    """Group stage matches only. Knockout matches use BracketSlot."""

    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    tournament_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    home_team_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("teams.id", ondelete="SET NULL")
    )
    away_team_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("teams.id", ondelete="SET NULL")
    )
    stage: Mapped[Stage] = mapped_column(_enum(Stage), nullable=False, index=True)
    kickoff_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stadium: Mapped[str | None] = mapped_column(String(120))

    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    # Penalty scores — populated only when match decided by shootout.
    penalty_home_score: Mapped[int | None] = mapped_column(Integer)
    penalty_away_score: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[MatchStatus] = mapped_column(
        _enum(MatchStatus), default=MatchStatus.SCHEDULED, nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(String(40), index=True)

    tournament: Mapped["Tournament"] = relationship(back_populates="matches")
    home_team: Mapped["Team | None"] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped["Team | None"] = relationship(foreign_keys=[away_team_id])
    predictions: Mapped[list["Prediction"]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )


class BracketSlot(Base):
    """An abstract position in the knockout bracket (R32 through Final).

    Seeded once at tournament setup from wc2026_bracket_slots.py.
    home_team_id / away_team_id are set when qualifying teams are known.
    Scores are set when the match is played.
    """

    __tablename__ = "bracket_slots"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    tournament_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    match_number: Mapped[int] = mapped_column(Integer, nullable=False)  # FIFA match # (73-104)
    stage: Mapped[Stage] = mapped_column(_enum(Stage), nullable=False, index=True)

    # Human-readable slot descriptions before teams are known.
    home_descriptor: Mapped[str] = mapped_column(String(60), nullable=False)
    away_descriptor: Mapped[str] = mapped_column(String(60), nullable=False)

    kickoff_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    venue: Mapped[str | None] = mapped_column(String(120))

    # Set when qualifying teams are known (admin action post-group-stage).
    home_team_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("teams.id", ondelete="SET NULL")
    )
    away_team_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("teams.id", ondelete="SET NULL")
    )

    # Actual results. penalty_* only populated when match decided by shootout.
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    penalty_home_score: Mapped[int | None] = mapped_column(Integer)
    penalty_away_score: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[MatchStatus] = mapped_column(
        _enum(MatchStatus), default=MatchStatus.SCHEDULED, nullable=False
    )

    tournament: Mapped["Tournament"] = relationship(back_populates="bracket_slots")
    home_team: Mapped["Team | None"] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped["Team | None"] = relationship(foreign_keys=[away_team_id])
    predictions: Mapped[list["BracketPrediction"]] = relationship(
        back_populates="slot", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("tournament_id", "match_number", name="uq_bracket_slot_per_tournament"),
    )


class PredictionWindow(Base):
    __tablename__ = "prediction_windows"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    tournament_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[Stage] = mapped_column(_enum(Stage), nullable=False)
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("tournament_id", "stage", name="uq_window_per_stage"),
    )


class Prediction(Base):
    """A user's predicted scoreline for a single GROUP STAGE match."""

    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    predicted_home_score: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_away_score: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    points_awarded: Mapped[int | None] = mapped_column(Integer)

    user: Mapped["User"] = relationship(back_populates="predictions")
    match: Mapped["Match"] = relationship(back_populates="predictions")

    __table_args__ = (
        UniqueConstraint("user_id", "match_id", name="uq_prediction_per_user_match"),
    )


class BracketPrediction(Base):
    """A user's predicted scoreline for a knockout bracket slot (R32-Final).

    Scoring is position-based: predicted_home > predicted_away means the user
    expects the home-position team to advance. Points are awarded when the slot
    has a confirmed result.
    """

    __tablename__ = "bracket_predictions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slot_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("bracket_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    predicted_home_score: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_away_score: Mapped[int] = mapped_column(Integer, nullable=False)
    # Derived team names, written by the scoring engine on every rescore.
    # These snapshot which teams the user's bracket implied for this slot,
    # so SQL audits can see teams without re-running the derivation.
    derived_home_team: Mapped[str | None] = mapped_column(String(80))
    derived_away_team: Mapped[str | None] = mapped_column(String(80))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    points_awarded: Mapped[int | None] = mapped_column(Integer)

    user: Mapped["User"] = relationship(back_populates="bracket_predictions")
    slot: Mapped["BracketSlot"] = relationship(back_populates="predictions")

    __table_args__ = (
        UniqueConstraint("user_id", "slot_id", name="uq_bracket_pred_per_user_slot"),
    )


class SpecialPrediction(Base):
    """Pre-tournament individual award and tournament stat predictions."""

    __tablename__ = "special_predictions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[SpecialCategory] = mapped_column(_enum(SpecialCategory), nullable=False)
    predicted_value: Mapped[str] = mapped_column(String(120), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    points_awarded: Mapped[int | None] = mapped_column(Integer)

    user: Mapped["User"] = relationship(back_populates="special_predictions")

    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_special_per_user_category"),
    )


class LeaderboardSnapshot(Base):
    """Materialised leaderboard rows with split match / award points."""

    __tablename__ = "leaderboard_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[Stage | None] = mapped_column(_enum(Stage))  # None => overall
    match_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    award_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EloCache(Base):
    """Persisted ELO ratings so they survive backend restarts.

    A single row per team, updated weekly via the scheduler.
    """

    __tablename__ = "elo_cache"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    team_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    rating: Mapped[float] = mapped_column(nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SpecialResult(Base):
    """Actual outcomes for special-prediction categories (admin-entered)."""

    __tablename__ = "special_results"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    tournament_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[SpecialCategory] = mapped_column(_enum(SpecialCategory), nullable=False)
    actual_value: Mapped[str] = mapped_column(String(120), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("tournament_id", "category", name="uq_special_result_per_category"),
    )
