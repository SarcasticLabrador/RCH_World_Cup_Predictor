"""SQLAlchemy ORM models for the World Cup Predictor.

Mirrors the agreed data model:
  users, magic_links, tournaments, teams, matches, prediction_windows,
  predictions, special_predictions, leaderboard_snapshots.
"""
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
from backend.enums import (
    MatchStatus,
    SpecialCategory,
    Stage,
    TournamentStatus,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Shorthand for native-enum-free storage (stores the value as a string, which
# is portable and keeps migrations painless).
def _enum(py_enum):
    return SAEnum(py_enum, native_enum=False, validate_strings=True, length=32)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(80))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    magic_links: Mapped[list["MagicLink"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    predictions: Mapped[list["Prediction"]] = relationship(
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

    teams: Mapped[list["Team"]] = relationship(
        back_populates="tournament", cascade="all, delete-orphan"
    )
    matches: Mapped[list["Match"]] = relationship(
        back_populates="tournament", cascade="all, delete-orphan"
    )


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    tournament_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    group: Mapped[str | None] = mapped_column(String(2))  # A..L (12 groups in 2026)
    flag_url: Mapped[str | None] = mapped_column(String(255))
    external_id: Mapped[str | None] = mapped_column(String(40), index=True)

    tournament: Mapped["Tournament"] = relationship(back_populates="teams")

    __table_args__ = (UniqueConstraint("tournament_id", "name", name="uq_team_per_tournament"),)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    tournament_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nullable: knockout fixtures exist before the qualifying teams are known.
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


class PredictionWindow(Base):
    """One window per stage. closes_at == kickoff of the first match in the stage."""

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
    """A user's predicted scoreline for a single match."""

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
    # Null until the match is scored.
    points_awarded: Mapped[int | None] = mapped_column(Integer)

    user: Mapped["User"] = relationship(back_populates="predictions")
    match: Mapped["Match"] = relationship(back_populates="predictions")

    __table_args__ = (
        UniqueConstraint("user_id", "match_id", name="uq_prediction_per_user_match"),
    )


class SpecialPrediction(Base):
    """Pre-tournament predictions: awards, champion, runner-up, team stats."""

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
    """Materialised leaderboard rows. stage=None means the overall board."""

    __tablename__ = "leaderboard_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[Stage | None] = mapped_column(_enum(Stage))  # None => overall
    total_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SpecialResult(Base):
    """Actual outcomes for special-prediction categories.

    Player awards (Golden Ball/Boot/Glove, Best Young Player) are entered here
    manually by the admin. Champion / runner-up / team-stat categories are
    auto-derived from match data, but a row here overrides the derived value.
    """

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
