"""Indian Trading Platform — Operator Console API.

Phase 4A: Backend API layer. All endpoints are testable via pytest and curl.
Phase 4B (Next.js frontend) is built separately.

Operating principle: "AI proposes. AI critiques. Rules decide.
Execution executes. Operator supervises."
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from packages.contracts.enums import Mode

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
        raw_mode = os.environ.get("MODE", Mode.PAPER.value)
        try:
            mode = Mode(raw_mode)
        except ValueError:
            mode = Mode.PAPER
        armed_live = os.environ.get("ARMED_LIVE", "false").lower() == "true"
        cfg = make_default_config(mode=mode, armed_live=armed_live)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://13.206.6.155:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
