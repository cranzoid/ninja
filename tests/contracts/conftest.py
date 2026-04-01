"""Shared fixtures for contract schema tests."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.contracts.enums import (
    BlockerCategory,
    ExecutionTiming,
    Mode,
    OrderSide,
    OrderType,
    PortfolioLayer,
    RegimeClass,
    SignalDirection,
)


@pytest.fixture
def utc_now() -> datetime:
    return datetime(2026, 3, 26, 9, 15, 0, tzinfo=UTC)


@pytest.fixture
def reliance_prices() -> dict:  # type: ignore[type-arg]
    return {
        "entry_price_target": Decimal("2850.00"),
        "stop_price": Decimal("2780.00"),
        "risk_per_share": Decimal("70.00"),
        "atr_14": Decimal("45.00"),
        "dma_200": Decimal("2650.00"),
        "dma_50": Decimal("2720.00"),
        "volume_ratio_20d": Decimal("1.45"),
    }


@pytest.fixture
def tcs_prices() -> dict:  # type: ignore[type-arg]
    return {
        "entry_price_target": Decimal("3820.00"),
        "stop_price": Decimal("3750.00"),
        "risk_per_share": Decimal("70.00"),
        "atr_14": Decimal("62.00"),
        "dma_200": Decimal("3700.00"),
        "dma_50": Decimal("3780.00"),
        "volume_ratio_20d": Decimal("0.95"),
    }


__all__ = [
    "BlockerCategory",
    "ExecutionTiming",
    "Mode",
    "OrderSide",
    "OrderType",
    "PortfolioLayer",
    "RegimeClass",
    "SignalDirection",
]
