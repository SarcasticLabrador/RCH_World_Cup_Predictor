"""Token-guarded task endpoints, for an external scheduler (e.g. GitHub Actions).

Set TASK_TOKEN in the environment and send it as the X-Task-Token header. This
lets you run maintenance/snapshots on a free host that sleeps, without an
always-on in-process scheduler.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.base import get_db
from backend.services import seeding, tasks

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _require_task_token(x_task_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.task_token:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task endpoints are disabled.")
    if x_task_token != settings.task_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid task token.")


@router.post("/maintenance", dependencies=[Depends(_require_task_token)])
def run_maintenance(db: Session = Depends(get_db)) -> dict:
    out = tasks.run_maintenance(db)
    db.commit()
    return out


@router.post("/snapshot", dependencies=[Depends(_require_task_token)])
def run_snapshot(db: Session = Depends(get_db)) -> dict:
    tournament = seeding.get_active_tournament(db)
    if tournament is None:
        return {"skipped": "no tournament seeded"}
    written = tasks.snapshot_leaderboard(db, tournament)
    db.commit()
    return {"snapshot_rows": written}
