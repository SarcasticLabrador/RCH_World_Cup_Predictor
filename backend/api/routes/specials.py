"""User special-predictions endpoints + team list (for dropdowns)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.db.base import get_db
from backend.db.models import User
from backend.schemas import (
    SpecialsOut,
    SubmitSpecialsIn,
    SubmitSpecialsOut,
    TeamOut,
)
from backend.services import seeding
from backend.services import specials as specials_service

router = APIRouter(prefix="/specials", tags=["specials"])


def _require_tournament(db: Session):
    tournament = seeding.get_active_tournament(db)
    if tournament is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No tournament has been seeded yet.")
    return tournament


@router.get("", response_model=SpecialsOut)
def get_specials(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SpecialsOut:
    tournament = _require_tournament(db)
    return SpecialsOut(
        state=specials_service.specials_state(db, tournament),
        categories=[c.value for c in specials_service.SPECIAL_ORDER],
        predictions=specials_service.get_user_specials(db, current),
    )


@router.post("", response_model=SubmitSpecialsOut)
def submit_specials(
    body: SubmitSpecialsIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubmitSpecialsOut:
    tournament = _require_tournament(db)
    items = [(p.category, p.value) for p in body.predictions]
    saved = specials_service.submit_specials(db, current, tournament, items)
    db.commit()
    return SubmitSpecialsOut(saved=saved)


@router.get("/teams", response_model=list[TeamOut])
def list_teams(
    _current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[TeamOut]:
    tournament = _require_tournament(db)
    return [
        TeamOut(name=t.name, group=t.group)
        for t in specials_service.list_teams(db, tournament)
    ]
