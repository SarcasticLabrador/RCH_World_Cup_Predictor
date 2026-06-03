"""User-facing special predictions (champion, runner-up, awards, team stats).

All eight categories are submitted pre-tournament and lock at the first
group-stage kickoff (i.e. when the group prediction window closes). We reuse
the group window's state as the specials window.
"""
from __future__ import annotations

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import SpecialPrediction, Team, Tournament, User
from backend.enums import SpecialCategory, Stage
from backend.services import predictions as pred_service

# Display/order of categories (labels live in the frontend).
SPECIAL_ORDER: list[SpecialCategory] = [
    SpecialCategory.CHAMPION,
    SpecialCategory.RUNNER_UP,
    SpecialCategory.GOLDEN_BALL,
    SpecialCategory.GOLDEN_BOOT,
    SpecialCategory.GOLDEN_GLOVE,
    SpecialCategory.BEST_YOUNG_PLAYER,
    SpecialCategory.MOST_GOALS_PER_GAME,
    SpecialCategory.FEWEST_CONCEDED_PER_GAME,
]


def specials_state(db: Session, tournament: Tournament) -> str:
    """'open' | 'closed' | 'pending' — driven by the group window."""
    group_window = pred_service.get_window(db, tournament, Stage.GROUP)
    state = pred_service.window_state(group_window)
    # Before fixtures exist the group window is 'pending'/'not_open_yet'.
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


def submit_specials(
    db: Session,
    user: User,
    tournament: Tournament,
    items: list[tuple],  # (category_str, value)
) -> int:
    if specials_state(db, tournament) != "open":
        raise HTTPException(
            http_status.HTTP_409_CONFLICT,
            "Special predictions are locked (the tournament has started).",
        )

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
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST, f"Unknown category '{category_str}'."
            )
        value = (value or "").strip()
        if not value:
            continue  # skip blanks; allows partial saves
        row = existing.get(category)
        if row is None:
            db.add(
                SpecialPrediction(
                    user_id=user.id, category=category, predicted_value=value[:120]
                )
            )
        else:
            row.predicted_value = value[:120]
        saved += 1

    db.flush()
    return saved
