"""Portfolio schemas — portfolio state and position tracking."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from .enums import PortfolioLayer


class Position(BaseModel):
    """A single open position in the portfolio."""

    model_config = ConfigDict(strict=True, frozen=True)

    symbol: str
    layer: PortfolioLayer
    quantity: int
    entry_price: Decimal
    current_price: Decimal
    stop_price: Decimal
    risk_amount: Decimal
    sector: str
    entry_date: date


class PortfolioState(BaseModel):
    """Snapshot of the current portfolio state."""

    model_config = ConfigDict(strict=True, frozen=True)

    equity: Decimal
    cash: Decimal
    positions: list[Position]
    open_risk_pct: Decimal
    sector_exposure: dict[str, Decimal]
