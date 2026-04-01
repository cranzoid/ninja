"""Tests for the stop & exit manager."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd
import pytest

from packages.contracts.enums import PortfolioLayer, RegimeClass
from packages.contracts.portfolio import Position
from packages.contracts.regime_state import RegimeState
from services.paper_broker.stop_manager import StopExitManager


def _regime(cls: RegimeClass = RegimeClass.GREEN) -> RegimeState:
    multipliers = {
        RegimeClass.GREEN: Decimal("1.0"),
        RegimeClass.MIXED: Decimal("0.5"),
        RegimeClass.STRESSED: Decimal("0.0"),
    }
    return RegimeState(
        assessed_at=datetime.now(UTC),
        regime_class=cls,
        nifty50_trend="bullish",
        breadth_above_50dma_pct=Decimal("72.5"),
        breadth_above_200dma_pct=Decimal("81.0"),
        vix_level=Decimal("14.2"),
        vix_state="normal",
        gap_frequency_5d=Decimal("1.0"),
        sector_concentration_score=Decimal("0.35"),
        correlation_state="normal",
        sizing_multiplier=multipliers[cls],
        rationale="Test regime.",
    )


def _swing_position(
    symbol: str = "RELIANCE",
    entry_price: Decimal = Decimal("2800"),
    current_price: Decimal = Decimal("2850"),
    stop_price: Decimal = Decimal("2620"),
    quantity: int = 10,
) -> Position:
    return Position(
        symbol=symbol,
        layer=PortfolioLayer.SWING,
        quantity=quantity,
        entry_price=entry_price,
        current_price=current_price,
        stop_price=stop_price,
        risk_amount=(entry_price - stop_price) * quantity,
        sector="energy",
        entry_date=date(2025, 12, 1),
    )


def _core_position(
    symbol: str = "TCS",
    entry_price: Decimal = Decimal("4000"),
    current_price: Decimal = Decimal("4100"),
    stop_price: Decimal = Decimal("3800"),
) -> Position:
    return Position(
        symbol=symbol,
        layer=PortfolioLayer.CORE,
        quantity=5,
        entry_price=entry_price,
        current_price=current_price,
        stop_price=stop_price,
        risk_amount=Decimal("1000"),
        sector="it",
        entry_date=date(2025, 10, 1),
    )


def _featured_df(
    close: float = 2850.0,
    dma_10: float = 2840.0,
    dma_200: float = 2500.0,
    n_rows: int = 5,
) -> pd.DataFrame:
    rows = []
    for i in range(n_rows):
        rows.append({
            "date": date(2025, 12, 10 + i),
            "open": close - 5,
            "high": close + 10,
            "low": close - 10,
            "close": close,
            "volume": 10_000_000,
            "dma_10": dma_10,
            "dma_200": dma_200,
        })
    return pd.DataFrame(rows)


class TestStopManager:
    @pytest.mark.asyncio
    async def test_stop_price_exit(self) -> None:
        """Position at stop price -> generates exit OrderIntent."""
        pos = _swing_position(stop_price=Decimal("2620"))
        data = {"RELIANCE": _featured_df(close=2610.0)}  # Below stop

        manager = StopExitManager()
        intents = await manager.evaluate_all_positions(
            [pos], data, date(2025, 12, 14), _regime()
        )

        assert len(intents) == 1
        assert intents[0].symbol == "RELIANCE"
        assert intents[0].side.value == "sell"

    @pytest.mark.asyncio
    async def test_partial_exit_at_2r(self) -> None:
        """Position at +2R -> generates partial exit OrderIntent."""
        # Entry 2800, stop 2620, risk = 180. +2R = 2800 + 360 = 3160
        pos = _swing_position(
            entry_price=Decimal("2800"),
            stop_price=Decimal("2620"),
            quantity=10,
        )
        data = {"RELIANCE": _featured_df(close=3170.0, dma_10=3165.0)}

        manager = StopExitManager()
        intents = await manager.evaluate_all_positions(
            [pos], data, date(2025, 12, 14), _regime()
        )

        assert len(intents) == 1
        assert intents[0].quantity == 5  # 50% partial exit

    @pytest.mark.asyncio
    async def test_trail_stop_10dma_exit(self) -> None:
        """Position below 10-DMA -> generates trail exit OrderIntent."""
        pos = _swing_position(
            entry_price=Decimal("2800"),
            stop_price=Decimal("2620"),
        )
        data = {"RELIANCE": _featured_df(close=2770.0, dma_10=2790.0)}

        manager = StopExitManager()
        intents = await manager.evaluate_all_positions(
            [pos], data, date(2025, 12, 14), _regime()
        )

        assert len(intents) == 1

    @pytest.mark.asyncio
    async def test_core_below_200dma_2_days_no_exit(self) -> None:
        """Core position below 200-DMA for 2 days -> no exit yet."""
        pos = _core_position()
        base = {"volume": 3_000_000, "dma_200": 4000, "dma_10": 4030}
        rows = [
            {"date": date(2025, 12, 10), "open": 4050, "high": 4060,
             "low": 4030, "close": 4050, **base},
            {"date": date(2025, 12, 11), "open": 3990, "high": 3995,
             "low": 3970, "close": 3980, **base},
            {"date": date(2025, 12, 12), "open": 3975, "high": 3985,
             "low": 3960, "close": 3970, **base},
        ]
        data = {"TCS": pd.DataFrame(rows)}

        manager = StopExitManager()
        intents = await manager.evaluate_all_positions(
            [pos], data, date(2025, 12, 12), _regime()
        )

        # Only 2 of 3 rows are below 200-DMA, so the 3-consecutive check
        # from the exit rules should NOT trigger
        assert len(intents) == 0

    @pytest.mark.asyncio
    async def test_core_below_200dma_3_days_exit(self) -> None:
        """Core position below 200-DMA for 3 days -> generates exit."""
        pos = _core_position()
        base = {"volume": 3_000_000, "dma_200": 4000, "dma_10": 4030}
        rows = [
            {"date": date(2025, 12, 10), "open": 3990, "high": 3995,
             "low": 3970, "close": 3980, **base},
            {"date": date(2025, 12, 11), "open": 3975, "high": 3985,
             "low": 3960, "close": 3970, **base},
            {"date": date(2025, 12, 12), "open": 3960, "high": 3975,
             "low": 3950, "close": 3960, **base},
        ]
        data = {"TCS": pd.DataFrame(rows)}

        manager = StopExitManager()
        intents = await manager.evaluate_all_positions(
            [pos], data, date(2025, 12, 12), _regime()
        )

        assert len(intents) == 1
        assert intents[0].symbol == "TCS"

    @pytest.mark.asyncio
    async def test_no_trigger_returns_empty(self) -> None:
        """No exit trigger hit -> empty list returned."""
        pos = _swing_position(
            entry_price=Decimal("2800"),
            stop_price=Decimal("2620"),
        )
        # Price at 2850, above stop, below 2R, above 10-DMA
        data = {"RELIANCE": _featured_df(close=2850.0, dma_10=2840.0)}

        manager = StopExitManager()
        intents = await manager.evaluate_all_positions(
            [pos], data, date(2025, 12, 14), _regime()
        )

        assert len(intents) == 0

    @pytest.mark.asyncio
    async def test_partial_exit_not_triggered_twice(self) -> None:
        """Partial exit not triggered twice for same position."""
        pos = _swing_position(
            entry_price=Decimal("2800"),
            stop_price=Decimal("2620"),
            quantity=10,
        )
        data = {"RELIANCE": _featured_df(close=3170.0, dma_10=3165.0)}

        manager = StopExitManager()

        # First evaluation: should trigger partial exit
        intents1 = await manager.evaluate_all_positions(
            [pos], data, date(2025, 12, 14), _regime()
        )
        assert len(intents1) == 1

        # Second evaluation with same position: should NOT trigger again
        intents2 = await manager.evaluate_all_positions(
            [pos], data, date(2025, 12, 15), _regime()
        )
        # Should be 0 — partial already taken
        assert len(intents2) == 0
