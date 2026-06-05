"""FastAPI application entrypoint.

Phase 1 wires up configuration, the database and a health route. Later phases
register additional routers here (auth, predictions, results, leaderboard, AI)
without needing to touch the existing wiring.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.routes import admin, ai, auth, bracket, health, leaderboard, odds, predictions, specials, tasks
from backend.config import get_settings
from backend.db.base import Base, engine
from backend.scheduler import shutdown_scheduler, start_scheduler

log = logging.getLogger(__name__)
settings = get_settings()


async def _prewarm_elo() -> None:
    """Download and compute ELO ratings in the background at startup.

    Runs in a thread so it doesn't block the event loop. The result is cached
    for 24 hours, so the first user request to /odds gets an instant response
    instead of waiting for the CSV download.
    """
    try:
        from backend.services.elo import fetch_elo_ratings
        await asyncio.get_event_loop().run_in_executor(None, fetch_elo_ratings)
        log.info("ELO ratings pre-warmed successfully")
    except Exception as exc:
        log.warning("ELO pre-warm failed (non-fatal): %s", exc)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    # Fire-and-forget: pre-warm ELO cache without blocking startup.
    asyncio.create_task(_prewarm_elo())
    try:
        yield
    finally:
        shutdown_scheduler()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(predictions.router)
app.include_router(bracket.router)
app.include_router(odds.router)
app.include_router(admin.router)
app.include_router(specials.router)
app.include_router(leaderboard.router)
app.include_router(tasks.router)
app.include_router(ai.router)


@app.get("/")
def root() -> dict:
    return {"app": settings.app_name, "docs": "/docs", "health": "/health"}
