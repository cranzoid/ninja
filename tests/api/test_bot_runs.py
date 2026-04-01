"""Tests for /api/runs endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestBotRuns:
    @pytest.mark.asyncio
    async def test_list_runs_returns_history(self, client: AsyncClient) -> None:
        """GET /api/runs returns EOD run history after simulation."""
        response = await client.get("/api/runs")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)
        # 3-day simulation = 3 reports
        assert body["total"] >= 3

    @pytest.mark.asyncio
    async def test_latest_run_returns_most_recent(self, client: AsyncClient) -> None:
        """GET /api/runs/latest returns the most recent run."""
        response = await client.get("/api/runs/latest")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "run_id" in data
        assert "trading_date" in data
        assert "regime" in data
        assert "reconciliation" in data
        assert "is_successful" in data

    @pytest.mark.asyncio
    async def test_get_run_by_id(self, client: AsyncClient) -> None:
        """GET /api/runs/{run_id} returns the specific run."""
        list_resp = await client.get("/api/runs")
        runs = list_resp.json()["data"]
        assert runs, "Expected at least one run in history"

        run_id = runs[0]["run_id"]
        response = await client.get(f"/api/runs/{run_id}")
        assert response.status_code == 200
        assert response.json()["data"]["run_id"] == run_id

    @pytest.mark.asyncio
    async def test_get_run_by_id_404(self, client: AsyncClient) -> None:
        """GET /api/runs/nonexistent → 404."""
        response = await client.get("/api/runs/no-such-run-id")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_runs_most_recent_first(self, client: AsyncClient) -> None:
        """Runs are returned most recent first."""
        response = await client.get("/api/runs")
        runs = response.json()["data"]
        if len(runs) >= 2:
            dates = [r["trading_date"] for r in runs]
            assert dates == sorted(dates, reverse=True)
