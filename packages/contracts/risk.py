"""Risk schemas — output of the risk engine calculator."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PortfolioRisk(BaseModel):
    """Calculated risk metrics for the portfolio."""

    model_config = ConfigDict(strict=True, frozen=True)

    total_equity: Decimal
    total_open_risk: Decimal
    open_risk_pct: Decimal
    position_count: int
    sector_exposure: dict[str, Decimal]
    largest_position_pct: Decimal
    is_within_limits: bool
    limit_breaches: list[str]
