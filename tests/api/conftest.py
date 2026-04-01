"""Shared fixtures for Phase 4A API tests.

Initializes AppState with fixture data, runs a 3-day simulation to populate
history, then provides an httpx AsyncClient with the dependency overridden.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from apps.api.src.dependencies import get_app_state
from apps.api.src.main import app
from apps.api.src.services.app_state import AppState, make_default_config

# Simulation range: Mon 5 Jan to Wed 7 Jan 2026 = 3 weekdays
_SIM_START = date(2026, 1, 5)
_SIM_END = date(2026, 1, 7)
_INITIAL_EQUITY = Decimal("500000")


@pytest_asyncio.fixture
async def app_state(tmp_path: Path) -> AppState:
    """AppState with fixture data and a 3-day simulation completed."""
    cfg = make_default_config()
    state = await AppState.initialize(tmp_path, cfg)
    await state.run_tracked_simulation(_SIM_START, _SIM_END, _INITIAL_EQUITY)
    return state


@pytest_asyncio.fixture
async def client(app_state: AppState) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient with the AppState dependency overridden."""
    app.dependency_overrides[get_app_state] = lambda: app_state
    app.state.app_state = app_state

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()
    if hasattr(app.state, "app_state"):
        del app.state.app_state
