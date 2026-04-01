"""Tests for GET /api/positions endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from apps.api.src.services.app_state import AppState


class TestPositions:
    @pytest.mark.asyncio
    async def test_list_positions_returns_paginated(self, client: AsyncClient) -> None:
        """GET /api/positions returns paginated response."""
        response = await client.get("/api/positions")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "data" in body
        assert "total" in body
        assert "page" in body
        assert "page_size" in body

    @pytest.mark.asyncio
    async def test_positions_enriched_fields(self, client: AsyncClient) -> None:
        """Positions include enriched fields like unrealized_pnl, days_held."""
        response = await client.get("/api/positions")
        assert response.status_code == 200
        positions = response.json()["data"]
        for pos in positions:
            assert "unrealized_pnl" in pos
            assert "unrealized_pnl_pct" in pos
            assert "risk_pct_of_equity" in pos
            assert "days_held" in pos
            assert "distance_to_stop_pct" in pos

    @pytest.mark.asyncio
    async def test_filter_by_layer_swing(self, client: AsyncClient) -> None:
        """Filter by layer=swing returns only swing positions."""
        response = await client.get("/api/positions?layer=swing")
        assert response.status_code == 200
        for pos in response.json()["data"]:
            assert pos["layer"] == "swing"

    @pytest.mark.asyncio
    async def test_filter_by_layer_core(self, client: AsyncClient) -> None:
        """Filter by layer=core returns only core positions."""
        response = await client.get("/api/positions?layer=core")
        assert response.status_code == 200
        for pos in response.json()["data"]:
            assert pos["layer"] == "core"

    @pytest.mark.asyncio
    async def test_sort_by_pnl(self, client: AsyncClient) -> None:
        """Sort by pnl desc returns positions ordered by unrealized_pnl."""
        response = await client.get("/api/positions?sort_by=pnl&sort_order=desc")
        assert response.status_code == 200
        positions = response.json()["data"]
        pnls = [float(p["unrealized_pnl"]) for p in positions]
        assert pnls == sorted(pnls, reverse=True)

    @pytest.mark.asyncio
    async def test_get_position_by_symbol_404(self, client: AsyncClient) -> None:
        """GET /api/positions/NONEXISTENT returns 404."""
        response = await client.get("/api/positions/NONEXISTENT")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_position_by_symbol_if_exists(
        self, client: AsyncClient, app_state: AppState
    ) -> None:
        """GET /api/positions/{symbol} returns PositionDetail for existing position."""
        positions = await app_state.paper_broker.get_positions()
        if not positions:
            pytest.skip("No positions open after simulation")

        symbol = positions[0].symbol
        response = await client.get(f"/api/positions/{symbol}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["symbol"] == symbol
        assert "unrealized_pnl" in data
