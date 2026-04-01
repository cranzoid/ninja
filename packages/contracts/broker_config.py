"""Broker configuration and quote schemas."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class PaperBrokerConfig(BaseModel):
    """Configuration for the paper broker."""

    model_config = ConfigDict(strict=True, frozen=True)

    slippage_bps: int = 5
    """Basis points of slippage to simulate (default 5 = 0.05%)."""

    fill_delay_bars: int = 1
    """Bars before fill (default 1 = next bar open)."""

    partial_fill_probability: Decimal = Decimal("0.0")
    """Chance of partial fill (default 0.0 for V1)."""

    reject_probability: Decimal = Decimal("0.0")
    """Chance of random rejection (default 0.0 for V1)."""

    data_dir: Path = Path("paper_broker_data")
    """Where to persist paper broker state."""


class Quote(BaseModel):
    """A market quote for a symbol."""

    model_config = ConfigDict(strict=True, frozen=True)

    symbol: str
    last_price: Decimal
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    timestamp: datetime
