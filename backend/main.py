"""FastAPI application entrypoint.

Phase 1 wires up configuration, the database and a health route. Later phases
register additional routers here (auth, predictions, results, leaderboard, AI)
without needing to touch the existing wiring.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.routes import admin, ai, auth, bracket, health, leaderboard, odds, predictions, specials, tasks
from backend.config import get_settings
from backend.db.base import Base, engine
from backend.scheduler import shutdown_scheduler, start_scheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # For Phase 1 we create tables directly. (Alembic migrations can be added
    # later if the schema starts changing in production.)
    Base.metadata.create_all(bind=engine)
    start_scheduler()
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
