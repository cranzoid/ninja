"""Tests for GET /api/dashboard."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestDashboard:
    @pytest.mark.asyncio
    async def test_dashboard_returns_valid_data(self, client: AsyncClient) -> None:
        """GET /api/dashboard returns valid DashboardData."""
        response = await client.get("/api/dashboard")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "mode" in data
        assert "portfolio_equity" in data
        assert "portfolio_cash" in data
        assert "total_positions" in data
        assert "regime" in data
        assert "system_health" in data
        assert "alerts_count_today" in data

    @pytest.mark.asyncio
    async def test_system_health_fields_present(self, client: AsyncClient) -> None:
        """System health reflects actual service state."""
        response = await client.get("/api/dashboard")
        assert response.status_code == 200
        health = response.json()["data"]["system_health"]
        assert "data_feed_fresh" in health
        assert "broker_healthy" in health
        assert "ledger_healthy" in health
        assert "last_run_successful" in health
        assert health["broker_healthy"] is True
        assert health["data_feed_fresh"] is True
        assert health["ledger_healthy"] is True

    @pytest.mark.asyncio
    async def test_dashboard_has_eod_run_after_simulation(
        self, client: AsyncClient
    ) -> None:
        """After a simulation, last_eod_run is populated."""
        response = await client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["last_eod_run"] is not None
        assert data["last_eod_run"]["is_successful"] is True

    @pytest.mark.asyncio
    async def test_dashboard_mode_is_paper(self, client: AsyncClient) -> None:
        """Dashboard reflects paper mode."""
        response = await client.get("/api/dashboard")
        assert response.status_code == 200
        assert response.json()["data"]["mode"] == "paper"
