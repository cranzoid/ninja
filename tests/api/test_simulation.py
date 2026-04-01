"""Tests for /api/simulation endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestSimulation:
    @pytest.mark.asyncio
    async def test_run_simulation_returns_summary(self, client: AsyncClient) -> None:
        """POST /api/simulation/run with 3-day range returns valid SimulationSummary."""
        payload = {
            "start_date": "2026-01-12",
            "end_date": "2026-01-14",
            "initial_equity": "500000",
        }
        response = await client.post("/api/simulation/run", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "simulation_id" in data
        assert "start_date" in data
        assert "end_date" in data
        assert "trading_days_run" in data
        assert data["trading_days_run"] == 3
        assert "total_return_pct" in data
        assert "max_drawdown_pct" in data

    @pytest.mark.asyncio
    async def test_simulation_history_updated_after_run(
        self, client: AsyncClient
    ) -> None:
        """After POST /api/simulation/run, history list includes new simulation."""
        payload = {
            "start_date": "2026-01-19",
            "end_date": "2026-01-21",
            "initial_equity": "500000",
        }
        run_resp = await client.post("/api/simulation/run", json=payload)
        sim_id = run_resp.json()["data"]["simulation_id"]

        list_resp = await client.get("/api/simulation/history")
        assert list_resp.status_code == 200
        sim_ids = [s["simulation_id"] for s in list_resp.json()["data"]]
        assert sim_id in sim_ids

    @pytest.mark.asyncio
    async def test_get_simulation_by_id(self, client: AsyncClient) -> None:
        """GET /api/simulation/{id} returns the specific simulation."""
        list_resp = await client.get("/api/simulation/history")
        sims = list_resp.json()["data"]
        assert sims, "Expected at least one simulation in history"

        sim_id = sims[0]["simulation_id"]
        response = await client.get(f"/api/simulation/{sim_id}")
        assert response.status_code == 200
        assert response.json()["data"]["simulation_id"] == sim_id

    @pytest.mark.asyncio
    async def test_get_simulation_404(self, client: AsyncClient) -> None:
        """GET /api/simulation/nonexistent → 404."""
        response = await client.get("/api/simulation/no-such-id")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_simulation_initial_equity_tracked(
        self, client: AsyncClient
    ) -> None:
        """Simulation summary tracks initial equity correctly."""
        payload = {
            "start_date": "2026-01-26",
            "end_date": "2026-01-28",
            "initial_equity": "750000",
        }
        response = await client.post("/api/simulation/run", json=payload)
        assert response.status_code == 200
        data = response.json()["data"]
        assert float(data["initial_equity"]) == 750000.0
