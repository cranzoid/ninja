"""Risk calculator — computes portfolio-level risk metrics."""

from __future__ import annotations

from decimal import Decimal

from packages.contracts.config_snapshot import RiskLimits
from packages.contracts.portfolio import Position
from packages.contracts.risk import PortfolioRisk


def calculate_portfolio_risk(
    positions: list[Position],
    equity: Decimal,
    risk_limits: RiskLimits | None = None,
) -> PortfolioRisk:
    """
    Calculate aggregate risk metrics for the portfolio.

    Checks against risk_limits if provided (defaults to charter limits).
    """
    limits = risk_limits or RiskLimits()

    if equity <= 0:
        return PortfolioRisk(
            total_equity=equity,
            total_open_risk=Decimal("0"),
            open_risk_pct=Decimal("0"),
            position_count=0,
            sector_exposure={},
            largest_position_pct=Decimal("0"),
            is_within_limits=True,
            limit_breaches=[],
        )

    total_risk = Decimal("0")
    sector_values: dict[str, Decimal] = {}
    largest_pct = Decimal("0")

    for pos in positions:
        total_risk += pos.risk_amount

        position_value = pos.current_price * pos.quantity
        position_pct = (position_value / equity) * 100
        if position_pct > largest_pct:
            largest_pct = position_pct

        prev = sector_values.get(pos.sector, Decimal("0"))
        sector_values[pos.sector] = prev + position_value

    open_risk_pct = (total_risk / equity) * 100
    sector_exposure = {
        sector: (value / equity) * 100
        for sector, value in sector_values.items()
    }

    # Check limits
    breaches: list[str] = []
    if open_risk_pct > limits.aggregate_open_risk_pct:
        breaches.append(
            f"aggregate_risk: {open_risk_pct:.2f}% > {limits.aggregate_open_risk_pct}%"
        )

    for sector, pct in sector_exposure.items():
        if pct > limits.sector_cap_pct:
            breaches.append(f"sector_{sector}: {pct:.2f}% > {limits.sector_cap_pct}%")

    return PortfolioRisk(
        total_equity=equity,
        total_open_risk=total_risk,
        open_risk_pct=open_risk_pct.quantize(Decimal("0.01")),
        position_count=len(positions),
        sector_exposure={
            k: v.quantize(Decimal("0.01"))
            for k, v in sector_exposure.items()
        },
        largest_position_pct=largest_pct.quantize(Decimal("0.01")),
        is_within_limits=len(breaches) == 0,
        limit_breaches=breaches,
    )
