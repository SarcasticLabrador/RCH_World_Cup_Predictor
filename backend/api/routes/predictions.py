"""Prediction endpoints: windows, stage fixtures, submission, reset, and admin seed."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_admin, get_current_user
from backend.db.base import get_db
from backend.db.models import User
from backend.enums import Stage
from backend.schemas import (
    FixtureOut,
    ResetPredictionsIn,
    SeedOut,
    StageFixturesOut,
    SubmitPredictionsIn,
    SubmitPredictionsOut,
    WindowOut,
)
from backend.services import predictions as pred_service
from backend.services import seeding

router = APIRouter(prefix="/predictions", tags=["predictions"])


def _require_tournament(db: Session):
    tournament = seeding.get_active_tournament(db)
    if tournament is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No tournament has been seeded yet.")
    return tournament


def _parse_stage(value: str) -> Stage:
    try:
        return Stage(value)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown stage '{value}'.")


@router.get("/windows", response_model=list[WindowOut])
def get_windows(
    _current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[WindowOut]:
    tournament = _require_tournament(db)
    windows = pred_service.list_windows(db, tournament)
    return [
        WindowOut(
            stage=w.stage.value,
            opens_at=w.opens_at,
            closes_at=w.closes_at,
            state=pred_service.window_state(w),
        )
        for w in sorted(windows, key=lambda w: (w.closes_at or w.stage.value))
    ]


@router.get("/fixtures", response_model=StageFixturesOut)
def get_stage_fixtures(
    stage: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StageFixturesOut:
    tournament = _require_tournament(db)
    stage_enum = _parse_stage(stage)
    window = pred_service.get_window(db, tournament, stage_enum)
    matches = pred_service.list_stage_matches(db, tournament, stage_enum)
    preds = pred_service.user_predictions_for_matches(db, current, [m.id for m in matches])

    fixtures = []
    for m in matches:
        p = preds.get(m.id)
        fixtures.append(
            FixtureOut(
                match_id=m.id,
                stage=m.stage.value,
                home_team=m.home_team.name if m.home_team else None,
                away_team=m.away_team.name if m.away_team else None,
                kickoff_utc=m.kickoff_utc,
                stadium=m.stadium,
                home_score=m.home_score,
                away_score=m.away_score,
                predicted_home_score=p.predicted_home_score if p else None,
                predicted_away_score=p.predicted_away_score if p else None,
            )
        )

    return StageFixturesOut(
        stage=stage_enum.value,
        state=pred_service.window_state(window),
        fixtures=fixtures,
    )


@router.post("", response_model=SubmitPredictionsOut)
def submit(
    body: SubmitPredictionsIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubmitPredictionsOut:
    tournament = _require_tournament(db)
    stage_enum = _parse_stage(body.stage)
    window = pred_service.get_window(db, tournament, stage_enum)
    if pred_service.window_state(window) != "open":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Prediction window is closed — no changes are possible.",
        )
    items = [(p.match_id, p.home_score, p.away_score) for p in body.predictions]
    saved = pred_service.submit_predictions(db, current, tournament, stage_enum, items)
    db.commit()
    return SubmitPredictionsOut(saved=saved)


@router.post("/reset", response_model=SubmitPredictionsOut)
def reset(
    body: ResetPredictionsIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubmitPredictionsOut:
    """Delete a user's predictions for a stage (or a single group within it)."""
    tournament = _require_tournament(db)
    stage_enum = _parse_stage(body.stage)
    window = pred_service.get_window(db, tournament, stage_enum)
    if pred_service.window_state(window) != "open":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Prediction window is closed — no changes are possible.",
        )
    deleted = pred_service.reset_predictions(db, current, tournament, stage_enum, body.group)
    db.commit()
    return SubmitPredictionsOut(saved=deleted)


@router.post("/admin/seed", response_model=SeedOut)
def admin_seed(
    _admin: User = Depends(get_current_admin), db: Session = Depends(get_db)
) -> SeedOut:
    """Seed the database from hardcoded 2026 World Cup fixtures."""
    from backend.services.wc2026_fixtures import get_2026_fixtures

    fixtures = get_2026_fixtures()
    stats = seeding.seed_world_cup(db, fixtures)
    db.commit()
    return SeedOut(**stats)
