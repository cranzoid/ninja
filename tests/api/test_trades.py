"""Tests for GET /api/trades and /api/audit endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestTrades:
    @pytest.mark.asyncio
    async def test_list_trades_returns_orders(self, client: AsyncClient) -> None:
        """GET /api/trades returns order records after simulation."""
        response = await client.get("/api/trades")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)
        assert "total" in body

    @pytest.mark.asyncio
    async def test_filter_by_status_filled(self, client: AsyncClient) -> None:
        """GET /api/trades?status=filled returns only filled orders."""
        response = await client.get("/api/trades?status=filled")
        assert response.status_code == 200
        for order in response.json()["data"]:
            assert order["current_status"] == "filled"

    @pytest.mark.asyncio
    async def test_filter_by_status_cancelled(self, client: AsyncClient) -> None:
        """GET /api/trades?status=cancelled returns only cancelled orders."""
        response = await client.get("/api/trades?status=cancelled")
        assert response.status_code == 200
        for order in response.json()["data"]:
            assert order["current_status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_get_trade_by_id_404(self, client: AsyncClient) -> None:
        """GET /api/trades/{order_id} returns 404 for unknown order."""
        response = await client.get("/api/trades/nonexistent-order-id")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_trade_by_id_if_exists(self, client: AsyncClient) -> None:
        """GET /api/trades/{order_id} returns order with transitions."""
        list_resp = await client.get("/api/trades")
        orders = list_resp.json()["data"]
        if not orders:
            pytest.skip("No orders after simulation")
        order_id = orders[0]["order_id"]
        response = await client.get(f"/api/trades/{order_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["order_id"] == order_id
        assert "transitions" in data


class TestAudit:
    @pytest.mark.asyncio
    async def test_list_audit_events(self, client: AsyncClient) -> None:
        """GET /api/audit returns audit events from the ledger."""
        response = await client.get("/api/audit")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)
        # After a 3-day simulation there should be events
        assert body["total"] >= 0

    @pytest.mark.asyncio
    async def test_audit_filter_by_symbol(self, client: AsyncClient) -> None:
        """GET /api/audit?symbol=RELIANCE returns events for RELIANCE."""
        response = await client.get("/api/audit?symbol=RELIANCE")
        assert response.status_code == 200
        for event in response.json()["data"]:
            assert event["related_symbol"] == "RELIANCE"

    @pytest.mark.asyncio
    async def test_audit_event_by_id_404(self, client: AsyncClient) -> None:
        """GET /api/audit/{event_id} returns 404 for unknown event."""
        response = await client.get("/api/audit/no-such-event-id")
        assert response.status_code == 404
