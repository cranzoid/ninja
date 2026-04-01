"""Indian Trading Platform — Operator Console API.

Phase 4A: Backend API layer. All endpoints are testable via pytest and curl.
Phase 4B (Next.js frontend) is built separately.

Operating principle: "AI proposes. AI critiques. Rules decide.
Execution executes. Operator supervises."
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .routers import (
    alerts,
    bot_runs,
    broker,
    commands,
    compliance,
    config,
    dashboard,
    live,
    model,
    plan,
    positions,
    regime,
    risk,
    shadow,
    simulation,
    trades,
)
from .services.app_state import AppState, make_default_config


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize AppState at startup if not already set (e.g., by tests)."""
    if not hasattr(app.state, "app_state"):
        cfg = make_default_config()
        state = await AppState.initialize(Path("./data"), cfg)
        app.state.app_state = state
    yield


app = FastAPI(
    title="Indian Trading Platform — Operator Console API",
    description=(
        "Phase 4A backend API for the operator console. "
        "Exposes paper trading state, EOD run history, risk metrics, "
        "and risk-reducing override commands."
    ),
    version="4.0.0",
    lifespan=lifespan,
)

# Health check (Phase 0, preserved)
@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


# Mount all routers
app.include_router(dashboard.router)
app.include_router(plan.router)
app.include_router(positions.router)
app.include_router(trades.router)
app.include_router(risk.router)
app.include_router(bot_runs.router)
app.include_router(config.router)
app.include_router(alerts.router)
app.include_router(commands.router)
app.include_router(compliance.router)
app.include_router(regime.router)
app.include_router(simulation.router)
app.include_router(model.router)
app.include_router(shadow.router)
app.include_router(broker.router)
app.include_router(live.router)
