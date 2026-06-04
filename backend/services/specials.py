"""User-facing individual award and tournament stat predictions."""
from __future__ import annotations

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import SpecialPrediction, Team, Tournament, User
from backend.enums import SpecialCategory, Stage
from backend.services import predictions as pred_service

SPECIAL_ORDER: list[SpecialCategory] = [
    SpecialCategory.GOLDEN_BALL,
    SpecialCategory.GOLDEN_BOOT,
    SpecialCategory.GOLDEN_GLOVE,
    SpecialCategory.BEST_YOUNG_PLAYER,
    SpecialCategory.TEAM_MOST_GOALS,
    SpecialCategory.TOTAL_GOALS,
    SpecialCategory.YELLOW_CARDS,
    SpecialCategory.RED_CARDS,
    SpecialCategory.FASTEST_GOAL,
    SpecialCategory.BIGGEST_MARGIN,
]

# Categories where user picks a team name (dropdown).
TEAM_SPECIALS: set[SpecialCategory] = {SpecialCategory.TEAM_MOST_GOALS}

# Categories where user enters a number.
NUMERIC_SPECIALS: set[SpecialCategory] = {
    SpecialCategory.TOTAL_GOALS,
    SpecialCategory.YELLOW_CARDS,
    SpecialCategory.RED_CARDS,
    SpecialCategory.FASTEST_GOAL,
    SpecialCategory.BIGGEST_MARGIN,
}


def specials_state(db: Session, tournament: Tournament) -> str:
    group_window = pred_service.get_window(db, tournament, Stage.GROUP)
    state = pred_service.window_state(group_window)
    if state in ("not_open_yet", "pending"):
        return "pending"
    return "open" if state == "open" else "closed"


def get_user_specials(db: Session, user: User) -> dict[str, str]:
    rows = db.scalars(
        select(SpecialPrediction).where(SpecialPrediction.user_id == user.id)
    ).all()
    return {r.category.value: r.predicted_value for r in rows}


def list_teams(db: Session, tournament: Tournament) -> list[Team]:
    return list(
        db.scalars(
            select(Team)
            .where(Team.tournament_id == tournament.id)
            .order_by(Team.group, Team.name)
        ).all()
    )


def submit_specials(db: Session, user: User, tournament: Tournament, items: list[tuple]) -> int:
    if specials_state(db, tournament) != "open":
        raise HTTPException(http_status.HTTP_409_CONFLICT,
                            "Individual picks are locked (the tournament has started).")

    existing = {
        r.category: r
        for r in db.scalars(
            select(SpecialPrediction).where(SpecialPrediction.user_id == user.id)
        ).all()
    }

    saved = 0
    for category_str, value in items:
        try:
            category = SpecialCategory(category_str)
        except ValueError:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST,
                                f"Unknown category '{category_str}'.")
        value = (value or "").strip()
        if not value:
            continue
        row = existing.get(category)
        if row is None:
            db.add(SpecialPrediction(
                user_id=user.id, category=category, predicted_value=value[:120]
            ))
        else:
            row.predicted_value = value[:120]
        saved += 1

    db.flush()
    return saved


def reset_specials(db: Session, user: User, tournament: Tournament) -> int:
    if specials_state(db, tournament) != "open":
        raise HTTPException(http_status.HTTP_409_CONFLICT,
                            "Individual picks are locked (the tournament has started).")
    deleted = (
        db.query(SpecialPrediction)
        .filter(SpecialPrediction.user_id == user.id)
        .delete(synchronize_session=False)
    )
    db.flush()
    return deleted
