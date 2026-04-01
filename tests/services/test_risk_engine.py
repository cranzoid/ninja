"""Tests for the risk engine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from packages.contracts.config_snapshot import RiskLimits
from packages.contracts.enums import PortfolioLayer
from packages.contracts.portfolio import Position
from services.risk_engine.calculator import calculate_portfolio_risk


def _position(
    symbol: str = "RELIANCE",
    sector: str = "energy",
    current_price: Decimal = Decimal("2800"),
    quantity: int = 10,
    risk_amount: Decimal = Decimal("900"),
) -> Position:
    return Position(
        symbol=symbol,
        layer=PortfolioLayer.SWING,
        quantity=quantity,
        entry_price=Decimal("2750"),
        current_price=current_price,
        stop_price=Decimal("2660"),
        risk_amount=risk_amount,
        sector=sector,
        entry_date=date(2025, 12, 1),
    )


class TestRiskCalculator:
    def test_within_limits(self) -> None:
        positions = [
            _position(symbol="RELIANCE", sector="energy", risk_amount=Decimal("900")),
            _position(symbol="TCS", sector="it", risk_amount=Decimal("700")),
        ]
        result = calculate_portfolio_risk(
            positions, Decimal("1000000"), RiskLimits()
        )
        assert result.is_within_limits is True
        assert result.position_count == 2
        assert float(result.open_risk_pct) < 4.0
        assert len(result.limit_breaches) == 0

    def test_aggregate_risk_breach(self) -> None:
        # Big risk amounts to exceed 4% aggregate
        positions = [
            _position(risk_amount=Decimal("25000")),
            _position(symbol="TCS", sector="it", risk_amount=Decimal("25000")),
        ]
        result = calculate_portfolio_risk(
            positions, Decimal("1000000"), RiskLimits()
        )
        assert result.is_within_limits is False
        assert any("aggregate_risk" in b for b in result.limit_breaches)

    def test_sector_cap_breach(self) -> None:
        # One sector with >25% of equity
        positions = [
            _position(
                symbol="RELIANCE",
                sector="energy",
                current_price=Decimal("2800"),
                quantity=100,
                risk_amount=Decimal("500"),
            ),
        ]
        # 2800 * 100 = 280,000 on 1M equity = 28%
        result = calculate_portfolio_risk(
            positions, Decimal("1000000"), RiskLimits()
        )
        assert result.is_within_limits is False
        assert any("sector_energy" in b for b in result.limit_breaches)

    def test_empty_portfolio(self) -> None:
        result = calculate_portfolio_risk([], Decimal("1000000"), RiskLimits())
        assert result.is_within_limits is True
        assert result.position_count == 0
        assert result.total_open_risk == Decimal("0")
        assert result.open_risk_pct == Decimal("0")
        assert result.largest_position_pct == Decimal("0")

    def test_sector_exposure_calculation(self) -> None:
        positions = [
            _position(
                symbol="RELIANCE", sector="energy",
                current_price=Decimal("2800"), quantity=10,
            ),
            _position(
                symbol="ONGC", sector="energy",
                current_price=Decimal("200"), quantity=100,
            ),
            _position(
                symbol="TCS", sector="it",
                current_price=Decimal("4000"), quantity=5,
            ),
        ]
        result = calculate_portfolio_risk(
            positions, Decimal("1000000"), RiskLimits()
        )
        assert "energy" in result.sector_exposure
        assert "it" in result.sector_exposure
        # energy: (2800*10 + 200*100) / 1M * 100 = 4.8%
        assert float(result.sector_exposure["energy"]) == 4.80
