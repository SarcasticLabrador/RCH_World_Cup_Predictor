"""Bracket slot retrieval and prediction submission endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.api.deps import get_current_admin, get_current_user
from backend.db.base import get_db
from backend.db.models import BracketPrediction, BracketSlot, Tournament, User
from backend.enums import MatchStatus
from backend.schemas import (
    BracketResultIn,
    BracketSlotsOut,
    BracketSlotOut,
    ScoreSummaryOut,
    SubmitBracketPredictionsIn,
    SubmitPredictionsOut,
)
from backend.services import bracket as bracket_svc
from backend.services import scoring, seeding

router = APIRouter(prefix="/bracket", tags=["bracket"])


def _tournament(db: Session) -> Tournament:
    t = seeding.get_active_tournament(db)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No tournament seeded yet.")
    return t


@router.get("/slots", response_model=BracketSlotsOut)
def get_slots(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BracketSlotsOut:
    """Return all bracket slots with user's predictions and derived teams.

    Seeds bracket slots automatically on first call if not yet present.
    """
    tournament = _tournament(db)

    existing_count = db.scalar(
        select(func.count(BracketSlot.id)).where(BracketSlot.tournament_id == tournament.id)
    )
    if not existing_count:
        seeding.seed_bracket_slots(db, tournament)
        db.commit()

    slots = db.scalars(
        select(BracketSlot)
        .where(BracketSlot.tournament_id == tournament.id)
        .order_by(BracketSlot.match_number)
    ).all()

    # User's bracket predictions.
    preds_map: dict[object, BracketPrediction] = {}
    for bp in db.scalars(
        select(BracketPrediction)
        .join(BracketSlot)
        .where(
            BracketSlot.tournament_id == tournament.id,
            BracketPrediction.user_id == current.id,
        )
    ).all():
        preds_map[bp.slot_id] = bp

    # On-the-fly bracket derivation for this user.
    try:
        derived = bracket_svc.derive_bracket(db, current, tournament)
    except Exception:
        derived = {}

    out = []
    for s in slots:
        bp = preds_map.get(s.id)
        d = derived.get(s.match_number)
        out.append(BracketSlotOut(
            slot_id=s.id,
            match_number=s.match_number,
            stage=s.stage.value,
            home_descriptor=s.home_descriptor,
            away_descriptor=s.away_descriptor,
            kickoff_utc=s.kickoff_utc,
            venue=s.venue,
            home_team=s.home_team.name if s.home_team else None,
            away_team=s.away_team.name if s.away_team else None,
            home_score=s.home_score,
            away_score=s.away_score,
            penalty_home_score=s.penalty_home_score,
            penalty_away_score=s.penalty_away_score,
            status=s.status.value,
            predicted_home_score=bp.predicted_home_score if bp else None,
            predicted_away_score=bp.predicted_away_score if bp else None,
            derived_home_team=d.home_team if d else None,
            derived_away_team=d.away_team if d else None,
        ))

    return BracketSlotsOut(slots=out)


@router.post("/predictions", response_model=SubmitPredictionsOut)
def submit_bracket_predictions(
    body: SubmitBracketPredictionsIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubmitPredictionsOut:
    """Upsert bracket slot predictions for the current user."""
    tournament = _tournament(db)
    # Bracket predictions are locked when the group window is closed
    # (triggered by /admin/lock-all which back-dates all closes_at to now).
    from backend.db.models import PredictionWindow
    from backend.enums import Stage as StageEnum
    from sqlalchemy import select as _select
    from datetime import datetime, timezone
    group_window = db.scalar(
        _select(PredictionWindow).where(
            PredictionWindow.tournament_id == tournament.id,
            PredictionWindow.stage == StageEnum.GROUP,
        )
    )
    now = datetime.now(timezone.utc)
    if group_window and group_window.closes_at and group_window.closes_at <= now:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "All predictions are locked — no changes are possible.",
        )

    valid_slot_ids = {
        s.id for s in db.scalars(
            select(BracketSlot).where(BracketSlot.tournament_id == tournament.id)
        ).all()
    }

    existing = {
        bp.slot_id: bp
        for bp in db.scalars(
            select(BracketPrediction)
            .join(BracketSlot)
            .where(
                BracketSlot.tournament_id == tournament.id,
                BracketPrediction.user_id == current.id,
            )
        ).all()
    }

    saved = 0
    for item in body.predictions:
        if item.slot_id not in valid_slot_ids:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"Slot {item.slot_id} not found in this tournament.")
        bp = existing.get(item.slot_id)
        if bp is None:
            db.add(BracketPrediction(
                user_id=current.id,
                slot_id=item.slot_id,
                predicted_home_score=item.home_score,
                predicted_away_score=item.away_score,
            ))
        else:
            bp.predicted_home_score = item.home_score
            bp.predicted_away_score = item.away_score
        saved += 1

    db.commit()
    return SubmitPredictionsOut(saved=saved)


@router.post("/admin/result", response_model=ScoreSummaryOut)
def set_bracket_result(
    body: BracketResultIn,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ScoreSummaryOut:
    """Set the result for a knockout bracket slot (admin only)."""
    tournament = _tournament(db)
    slot = db.scalar(
        select(BracketSlot).where(
            BracketSlot.tournament_id == tournament.id,
            BracketSlot.match_number == body.match_number,
        )
    )
    if slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"Bracket slot {body.match_number} not found.")

    if body.finished:
        slot.home_score = body.home_score
        slot.away_score = body.away_score
        slot.penalty_home_score = body.penalty_home_score
        slot.penalty_away_score = body.penalty_away_score
        slot.status = MatchStatus.FINISHED
    else:
        slot.home_score = slot.away_score = None
        slot.penalty_home_score = slot.penalty_away_score = None
        slot.status = MatchStatus.SCHEDULED

    summary = scoring.score_tournament(db, tournament)
    db.commit()
    return ScoreSummaryOut(**summary)
