"""Phase 5 tests — Model API endpoints."""

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

_SIM_START = date(2026, 1, 5)
_SIM_END = date(2026, 1, 7)
_INITIAL_EQUITY = Decimal("500000")


@pytest_asyncio.fixture
async def app_state(tmp_path: Path) -> AppState:
    cfg = make_default_config()
    state = await AppState.initialize(tmp_path, cfg)
    await state.run_tracked_simulation(_SIM_START, _SIM_END, _INITIAL_EQUITY)
    return state


@pytest_asyncio.fixture
async def client(app_state: AppState) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_app_state] = lambda: app_state
    app.state.app_state = app_state

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()
    if hasattr(app.state, "app_state"):
        del app.state.app_state


class TestModelHealthEndpoint:
    async def test_health_returns_provider_status(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/api/model/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "fixture" in data["data"]
        assert data["data"]["fixture"]["is_healthy"] is True

    async def test_health_response_structure(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/api/model/health")
        body = response.json()
        fixture_data = body["data"]["fixture"]
        assert "latency_ms" in fixture_data
        assert "last_checked" in fixture_data


class TestModelTelemetryEndpoint:
    async def test_telemetry_returns_summary(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/api/model/telemetry")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "total_calls" in data["data"]
        assert "stats" in data["data"]

    async def test_telemetry_after_blocker_scan(
        self, client: AsyncClient
    ) -> None:
        # First do a blocker scan
        await client.post(
            "/api/model/blocker-scan",
            json={
                "symbol": "RELIANCE",
                "headlines": ["Test"],
                "price": 2850.0,
                "atr": 45.0,
            },
        )
        # Then check telemetry
        response = await client.get("/api/model/telemetry")
        data = response.json()
        assert data["data"]["total_calls"] >= 1


class TestBlockerScanEndpoint:
    async def test_blocker_scan_returns_report(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/model/blocker-scan",
            json={
                "symbol": "RELIANCE",
                "headlines": ["Reliance steady quarter"],
                "price": 2850.0,
                "atr": 45.0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["symbol"] == "RELIANCE"

    async def test_blocker_scan_with_blocker(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/model/blocker-scan",
            json={
                "symbol": "HDFCBANK",
                "headlines": ["HDFC Bank Q4 results expected"],
                "price": 1650.0,
                "atr": 30.0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["symbol"] == "HDFCBANK"
        assert data["data"]["is_blocked"] is True
