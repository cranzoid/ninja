"""Tests for /api/plan endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestPlan:
    @pytest.mark.asyncio
    async def test_todays_plan_returns_valid_data(self, client: AsyncClient) -> None:
        """GET /api/plan/today returns valid TodaysPlan."""
        response = await client.get("/api/plan/today")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "trading_date" in data
        assert "regime" in data
        assert "pending_entries" in data
        assert "pending_exits" in data
        assert "exit_watchlist" in data
        assert "candidate_preview" in data
        assert "blocked_symbols" in data

    @pytest.mark.asyncio
    async def test_pending_entries_are_buy_orders(self, client: AsyncClient) -> None:
        """pending_entries contain only BUY-side orders."""
        response = await client.get("/api/plan/today")
        assert response.status_code == 200
        for entry in response.json()["data"]["pending_entries"]:
            assert entry["intent"]["side"] == "buy"

    @pytest.mark.asyncio
    async def test_pending_exits_are_sell_orders(self, client: AsyncClient) -> None:
        """pending_exits contain only SELL-side orders."""
        response = await client.get("/api/plan/today")
        assert response.status_code == 200
        for exit_order in response.json()["data"]["pending_exits"]:
            assert exit_order["intent"]["side"] == "sell"

    @pytest.mark.asyncio
    async def test_run_eod_returns_report(self, client: AsyncClient) -> None:
        """POST /api/plan/run-eod triggers a run and returns EODRunReport."""
        payload = {"trading_date": "2026-01-08"}  # Thursday
        response = await client.post("/api/plan/run-eod", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "run_id" in data
        assert "trading_date" in data
        assert data["trading_date"] == "2026-01-08"
        assert "regime" in data
        assert "reconciliation" in data

    @pytest.mark.asyncio
    async def test_run_eod_adds_to_history(self, client: AsyncClient) -> None:
        """After POST /api/plan/run-eod, GET /api/runs/latest reflects new run."""
        payload = {"trading_date": "2026-01-09"}
        run_resp = await client.post("/api/plan/run-eod", json=payload)
        new_run_id = run_resp.json()["data"]["run_id"]

        latest_resp = await client.get("/api/runs/latest")
        assert latest_resp.status_code == 200
        assert latest_resp.json()["data"]["run_id"] == new_run_id
