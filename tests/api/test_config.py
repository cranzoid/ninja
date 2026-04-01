"""Tests for /api/config endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestConfig:
    @pytest.mark.asyncio
    async def test_current_config_returns_snapshot(self, client: AsyncClient) -> None:
        """GET /api/config/current returns valid ConfigSnapshot."""
        response = await client.get("/api/config/current")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "snapshot_id" in data
        assert "mode" in data
        assert "risk_limits" in data
        assert "armed_live" in data
        assert data["mode"] == "paper"
        assert data["armed_live"] is False

    @pytest.mark.asyncio
    async def test_risk_limits_returns_limits(self, client: AsyncClient) -> None:
        """GET /api/config/risk-limits returns RiskLimits."""
        response = await client.get("/api/config/risk-limits")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        limits = body["data"]
        assert "swing_risk_per_trade_pct" in limits
        assert "core_add_risk_pct" in limits
        assert "sector_cap_pct" in limits
        assert "aggregate_open_risk_pct" in limits
        assert float(limits["swing_risk_per_trade_pct"]) == 0.5
        assert float(limits["aggregate_open_risk_pct"]) == 4.0

    @pytest.mark.asyncio
    async def test_config_history_grows_after_eod(self, client: AsyncClient) -> None:
        """Config history grows after EOD runs (one snapshot per run)."""
        history_before = await client.get("/api/config/history")
        count_before = history_before.json()["total"]

        # Run an additional EOD
        await client.post(
            "/api/plan/run-eod", json={"trading_date": "2026-02-02"}
        )

        history_after = await client.get("/api/config/history")
        count_after = history_after.json()["total"]
        assert count_after > count_before

    @pytest.mark.asyncio
    async def test_config_diff_with_same_snapshot_no_changes(
        self, client: AsyncClient
    ) -> None:
        """Diff of a snapshot against itself has zero changes."""
        snap_resp = await client.get("/api/config/current")
        snap_id = snap_resp.json()["data"]["snapshot_id"]

        diff_resp = await client.get(
            f"/api/config/diff?snapshot_id_a={snap_id}&snapshot_id_b={snap_id}"
        )
        assert diff_resp.status_code == 200
        changes = diff_resp.json()["data"]["changes"]
        assert changes == []
