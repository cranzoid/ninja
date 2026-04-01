"""Phase 6 tests — API endpoints (10+ tests)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
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


class TestComplianceEndpoints:
    @pytest.mark.asyncio
    async def test_get_compliance_status(self, client: AsyncClient) -> None:
        resp = await client.get("/api/compliance/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        # Phase 7: response is now {report: {...}, live_ready: bool}
        report = data["report"]
        assert "results" in report
        assert "all_blocking_passed" in report
        assert "mode" in report

    @pytest.mark.asyncio
    async def test_compliance_status_has_all_checks(self, client: AsyncClient) -> None:
        resp = await client.get("/api/compliance/status")
        body = resp.json()
        results = body["data"]["report"]["results"]
        check_names = {r["check_name"] for r in results}
        # Should have all 8 checks
        assert "env_vars" in check_names
        assert "kill_switch" in check_names
        assert "mode_flag" in check_names
        assert "broker_auth" in check_names
        assert "broker_health" in check_names
        assert "audit_sink" in check_names
        assert "config_checksum" in check_names
        assert "clock_check" in check_names

    @pytest.mark.asyncio
    async def test_post_compliance_run(self, client: AsyncClient) -> None:
        resp = await client.post("/api/compliance/run")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "results" in body["data"]

    @pytest.mark.asyncio
    async def test_compliance_returns_real_report(self, client: AsyncClient) -> None:
        resp = await client.get("/api/compliance/status")
        body = resp.json()
        report = body["data"]["report"]
        # Should return ComplianceReport format
        assert "generated_at" in report
        assert "all_blocking_passed" in report


class TestShadowEndpoints:
    @pytest.mark.asyncio
    async def test_post_shadow_run_eod(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/shadow/run-eod",
            json={"trading_date": "2026-01-06"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["trading_date"] == "2026-01-06"
        assert "candidates_scanned" in data
        assert "intents_generated" in data

    @pytest.mark.asyncio
    async def test_shadow_run_eod_invalid_date(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/shadow/run-eod",
            json={"trading_date": "not-a-date"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "Invalid date" in body["error"]

    @pytest.mark.asyncio
    async def test_get_shadow_runs_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/api/shadow/runs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)

    @pytest.mark.asyncio
    async def test_get_shadow_runs_after_run(self, client: AsyncClient) -> None:
        # Run a shadow EOD first
        await client.post(
            "/api/shadow/run-eod",
            json={"trading_date": "2026-01-06"},
        )
        resp = await client.get("/api/shadow/runs")
        body = resp.json()
        assert body["total"] >= 1


class TestBrokerEndpoints:
    @pytest.mark.asyncio
    async def test_get_broker_health(self, client: AsyncClient) -> None:
        resp = await client.get("/api/broker/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["is_healthy"] is True
        assert "latency_ms" in data

    @pytest.mark.asyncio
    async def test_get_broker_session_no_active(self, client: AsyncClient) -> None:
        resp = await client.get("/api/broker/session")
        assert resp.status_code == 200
        body = resp.json()
        # No session yet — should return error
        assert body["success"] is False
        assert "No active" in body["error"]

    @pytest.mark.asyncio
    async def test_get_broker_session_after_auth(
        self, client: AsyncClient, app_state: AppState
    ) -> None:
        # Authenticate first
        assert app_state.mock_broker is not None
        await app_state.mock_broker.authenticate()

        resp = await client.get("/api/broker/session")
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["broker_name"] == "mock"
        assert "session_id" in data
