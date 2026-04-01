"""Tests for the command center — operator override commands."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from apps.api.src.services.app_state import AppState


class TestCommandCenter:
    @pytest.mark.asyncio
    async def test_freeze_symbol_executed(self, client: AsyncClient) -> None:
        """POST FREEZE_SYMBOL → executed, symbol appears in frozen list."""
        cmd = {
            "command_type": "freeze_symbol",
            "symbol": "RELIANCE",
            "parameters": {},
            "reason": "Testing freeze functionality",
        }
        response = await client.post("/api/commands/execute", json=cmd)
        assert response.status_code == 200
        result = response.json()["data"]
        assert result["status"] == "executed"
        assert result["symbol"] == "RELIANCE"

        # Verify it appears in frozen list
        frozen_resp = await client.get("/api/commands/frozen-symbols")
        assert frozen_resp.status_code == 200
        frozen = frozen_resp.json()["data"]
        assert "RELIANCE" in frozen

    @pytest.mark.asyncio
    async def test_unfreeze_symbol(self, client: AsyncClient) -> None:
        """Freeze then unfreeze removes symbol from frozen list."""
        # Freeze first
        await client.post(
            "/api/commands/execute",
            json={
                "command_type": "freeze_symbol",
                "symbol": "TCS",
                "parameters": {},
                "reason": "freeze for test",
            },
        )

        # Unfreeze
        unfreeze_resp = await client.post(
            "/api/commands/unfreeze/TCS",
            json={"reason": "test unfreeze"},
        )
        assert unfreeze_resp.status_code == 200
        assert unfreeze_resp.json()["success"] is True

        # Verify removed
        frozen_resp = await client.get("/api/commands/frozen-symbols")
        frozen = frozen_resp.json()["data"]
        assert "TCS" not in frozen

    @pytest.mark.asyncio
    async def test_close_position_if_exists(
        self, client: AsyncClient, app_state: AppState
    ) -> None:
        """POST CLOSE_POSITION → executed and resulting_order is set."""
        positions = await app_state.paper_broker.get_positions()
        if not positions:
            pytest.skip("No open positions after simulation")

        symbol = positions[0].symbol
        cmd = {
            "command_type": "close_position",
            "symbol": symbol,
            "parameters": {},
            "reason": "Test close",
        }
        response = await client.post("/api/commands/execute", json=cmd)
        assert response.status_code == 200
        result = response.json()["data"]
        assert result["status"] == "executed"
        assert result["resulting_order"] is not None

    @pytest.mark.asyncio
    async def test_close_position_no_position_rejected(
        self, client: AsyncClient
    ) -> None:
        """POST CLOSE_POSITION for non-existent position → rejected."""
        cmd = {
            "command_type": "close_position",
            "symbol": "NONEXISTENT",
            "parameters": {},
            "reason": "Test rejection",
        }
        response = await client.post("/api/commands/execute", json=cmd)
        assert response.status_code == 200
        result = response.json()["data"]
        assert result["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_reduce_size_must_be_less_than_current(
        self, client: AsyncClient, app_state: AppState
    ) -> None:
        """POST REDUCE_SIZE with new_size >= current_qty → rejected."""
        positions = await app_state.paper_broker.get_positions()
        if not positions:
            pytest.skip("No open positions after simulation")

        pos = positions[0]
        cmd = {
            "command_type": "reduce_size",
            "symbol": pos.symbol,
            "parameters": {"new_size": pos.quantity + 10},
            "reason": "Test rejection",
        }
        response = await client.post("/api/commands/execute", json=cmd)
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_tighten_stop_must_be_higher_than_current(
        self, client: AsyncClient, app_state: AppState
    ) -> None:
        """POST TIGHTEN_STOP with new_stop <= current_stop → rejected."""
        positions = await app_state.paper_broker.get_positions()
        if not positions:
            pytest.skip("No open positions after simulation")

        pos = positions[0]
        lower_stop = float(pos.stop_price) - 50
        cmd = {
            "command_type": "tighten_stop",
            "symbol": pos.symbol,
            "parameters": {"new_stop": str(lower_stop)},
            "reason": "Test rejection",
        }
        response = await client.post("/api/commands/execute", json=cmd)
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_tighten_stop_executed(
        self, client: AsyncClient, app_state: AppState
    ) -> None:
        """POST TIGHTEN_STOP with valid higher stop → executed."""
        positions = await app_state.paper_broker.get_positions()
        if not positions:
            pytest.skip("No open positions after simulation")

        pos = positions[0]
        higher_stop = float(pos.stop_price) + 10
        cmd = {
            "command_type": "tighten_stop",
            "symbol": pos.symbol,
            "parameters": {"new_stop": str(higher_stop)},
            "reason": "Tightening for test",
        }
        response = await client.post("/api/commands/execute", json=cmd)
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "executed"

    @pytest.mark.asyncio
    async def test_empty_reason_rejected_422(self, client: AsyncClient) -> None:
        """POST with empty reason → 422 validation error."""
        cmd = {
            "command_type": "freeze_symbol",
            "symbol": "INFY",
            "parameters": {},
            "reason": "",
        }
        response = await client.post("/api/commands/execute", json=cmd)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_command_history(self, client: AsyncClient) -> None:
        """GET /api/commands/history returns override events."""
        # First do a freeze to generate a command
        await client.post(
            "/api/commands/execute",
            json={
                "command_type": "freeze_symbol",
                "symbol": "SBIN",
                "parameters": {},
                "reason": "history test",
            },
        )
        response = await client.get("/api/commands/history")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

    @pytest.mark.asyncio
    async def test_frozen_symbols_list(self, client: AsyncClient) -> None:
        """GET /api/commands/frozen-symbols returns list."""
        response = await client.get("/api/commands/frozen-symbols")
        assert response.status_code == 200
        assert isinstance(response.json()["data"], list)
