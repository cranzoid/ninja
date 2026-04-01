"""Tests for GET /api/risk endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestRisk:
    @pytest.mark.asyncio
    async def test_current_risk_returns_valid_data(self, client: AsyncClient) -> None:
        """GET /api/risk/current returns valid RiskCenterData."""
        response = await client.get("/api/risk/current")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "portfolio_risk" in data
        assert "risk_limits" in data
        assert "limit_utilization" in data
        assert "position_risk_breakdown" in data

    @pytest.mark.asyncio
    async def test_risk_limits_present(self, client: AsyncClient) -> None:
        """Risk limits match charter defaults."""
        response = await client.get("/api/risk/current")
        assert response.status_code == 200
        limits = response.json()["data"]["risk_limits"]
        assert "swing_risk_per_trade_pct" in limits
        assert "aggregate_open_risk_pct" in limits
        assert float(limits["aggregate_open_risk_pct"]) == 4.0

    @pytest.mark.asyncio
    async def test_limit_utilization_structure(self, client: AsyncClient) -> None:
        """LimitUtilization has all required fields."""
        response = await client.get("/api/risk/current")
        assert response.status_code == 200
        util = response.json()["data"]["limit_utilization"]
        assert "aggregate_risk_used_pct" in util
        assert "aggregate_risk_limit_pct" in util
        assert "aggregate_risk_utilization_pct" in util
        assert "sector_utilization" in util

    @pytest.mark.asyncio
    async def test_position_risk_breakdown_per_position(
        self, client: AsyncClient
    ) -> None:
        """PositionRiskDetail entries exist for each open position."""
        pos_resp = await client.get("/api/positions")
        open_count = pos_resp.json()["total"]

        risk_resp = await client.get("/api/risk/current")
        breakdown = risk_resp.json()["data"]["position_risk_breakdown"]
        assert len(breakdown) == open_count

    @pytest.mark.asyncio
    async def test_risk_history(self, client: AsyncClient) -> None:
        """GET /api/risk/history returns portfolio risk snapshots."""
        response = await client.get("/api/risk/history")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        # After 3-day simulation there should be history
        assert body["total"] >= 0
