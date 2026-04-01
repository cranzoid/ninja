"""Tests for the rule engine — the most critical Phase 2 module."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd

from packages.contracts.blocker_report import BlockerDetail, BlockerReport
from packages.contracts.candidates import SwingCandidate
from packages.contracts.config_snapshot import RiskLimits
from packages.contracts.enums import (
    BlockerCategory,
    PortfolioLayer,
    RegimeClass,
)
from packages.contracts.portfolio import PortfolioState, Position
from packages.contracts.regime_state import RegimeState
from services.rule_engine.entry_rules import evaluate_swing_entry
from services.rule_engine.exit_rules import evaluate_exits
from services.rule_engine.position_sizer import calculate_position_size

# --- Helpers ---


def _regime(cls: RegimeClass = RegimeClass.GREEN) -> RegimeState:
    multipliers = {
        RegimeClass.GREEN: Decimal("1.0"),
        RegimeClass.MIXED: Decimal("0.5"),
        RegimeClass.STRESSED: Decimal("0.0"),
    }
    return RegimeState(
        assessed_at=datetime.now(UTC),
        regime_class=cls,
        nifty50_trend="bullish" if cls == RegimeClass.GREEN else "bearish",
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


def _candidate(
    symbol: str = "RELIANCE",
    close: Decimal = Decimal("2800"),
    risk_per_share: Decimal = Decimal("200"),
    atr_14: Decimal = Decimal("100"),
) -> SwingCandidate:
    return SwingCandidate(
        symbol=symbol,
        scan_date=date(2025, 12, 15),
        close=close,
        entry_price_estimate=close,
        stop_price=close - risk_per_share,
        risk_per_share=risk_per_share,
        volume_ratio=Decimal("1.5"),
        atr_14=atr_14,
        regime_at_scan=RegimeClass.GREEN,
        passes_all_entry_conditions=True,
        failed_conditions=[],
    )


def _portfolio(
    equity: Decimal = Decimal("10000000"),
    cash: Decimal = Decimal("5000000"),
    open_risk_pct: Decimal = Decimal("1.0"),
    positions: list[Position] | None = None,
) -> PortfolioState:
    return PortfolioState(
        equity=equity,
        cash=cash,
        positions=positions or [],
        open_risk_pct=open_risk_pct,
        sector_exposure={},
    )


def _clean_blockers(symbol: str = "RELIANCE") -> BlockerReport:
    return BlockerReport(
        symbol=symbol,
        scan_timestamp=datetime.now(UTC),
        blockers_found=[],
        is_blocked=False,
        model_provider="anthropic",
        model_id="claude-haiku-4-5",
    )


def _hard_blocker(symbol: str = "RELIANCE") -> BlockerReport:
    return BlockerReport(
        symbol=symbol,
        scan_timestamp=datetime.now(UTC),
        blockers_found=[
            BlockerDetail(
                category=BlockerCategory.EARNINGS_WINDOW,
                severity="hard",
                reason="Q4 results in 3 days.",
                source_category="earnings_calendar",
            )
        ],
        is_blocked=True,
        model_provider="anthropic",
        model_id="claude-haiku-4-5",
    )


# --- Entry rule tests ---


class TestEntryRules:
    def test_approved_entry(self) -> None:
        decision = evaluate_swing_entry(
            _candidate(),
            _portfolio(),
            RiskLimits(),
            _regime(),
            _clean_blockers(),
        )
        assert decision.decision == "approve"
        assert decision.order_intent is not None
        assert decision.order_intent.symbol == "RELIANCE"
        assert decision.order_intent.layer == PortfolioLayer.SWING
        assert len(decision.checks_performed) > 0

    def test_blocked_by_hard_blocker(self) -> None:
        decision = evaluate_swing_entry(
            _candidate(),
            _portfolio(),
            RiskLimits(),
            _regime(),
            _hard_blocker(),
        )
        assert decision.decision == "reject"
        assert any("hard_blocker" in r for r in decision.rejection_reasons)
        assert "blocker_check" in decision.checks_performed

    def test_rejected_stressed_regime(self) -> None:
        decision = evaluate_swing_entry(
            _candidate(),
            _portfolio(),
            RiskLimits(),
            _regime(RegimeClass.STRESSED),
            _clean_blockers(),
        )
        assert decision.decision == "reject"
        assert any("regime_stressed" in r for r in decision.rejection_reasons)

    def test_mixed_regime_half_sized(self) -> None:
        decision = evaluate_swing_entry(
            _candidate(),
            _portfolio(),
            RiskLimits(),
            _regime(RegimeClass.MIXED),
            _clean_blockers(),
        )
        assert decision.decision == "approve"
        assert decision.order_intent is not None

        # Compare with green regime sizing
        green_decision = evaluate_swing_entry(
            _candidate(),
            _portfolio(),
            RiskLimits(),
            _regime(RegimeClass.GREEN),
            _clean_blockers(),
        )
        assert green_decision.order_intent is not None
        # Mixed should have roughly half the quantity
        assert decision.order_intent.quantity < green_decision.order_intent.quantity

    def test_aggregate_risk_breach(self) -> None:
        # Portfolio already at 3.8% risk, limit is 4%
        decision = evaluate_swing_entry(
            _candidate(),
            _portfolio(open_risk_pct=Decimal("3.8")),
            RiskLimits(),
            _regime(),
            _clean_blockers(),
        )
        assert decision.decision == "reject"
        assert any("aggregate_risk" in r for r in decision.rejection_reasons)

    def test_position_size_zero_small_capital(self) -> None:
        # Very small equity with expensive stock → 0 shares
        decision = evaluate_swing_entry(
            _candidate(close=Decimal("50000"), risk_per_share=Decimal("5000")),
            _portfolio(
                equity=Decimal("10000"),
                cash=Decimal("10000"),
                open_risk_pct=Decimal("0"),
            ),
            RiskLimits(),
            _regime(),
            _clean_blockers(),
        )
        assert decision.decision == "reject"
        assert any("position_size_zero" in r for r in decision.rejection_reasons)

    def test_all_checks_logged(self) -> None:
        decision = evaluate_swing_entry(
            _candidate(),
            _portfolio(),
            RiskLimits(),
            _regime(),
            _clean_blockers(),
        )
        assert "blocker_check" in decision.checks_performed
        assert "regime_check" in decision.checks_performed
        assert "aggregate_risk_check" in decision.checks_performed


# --- Exit rule tests ---


def _swing_position(
    symbol: str = "RELIANCE",
    entry_price: Decimal = Decimal("2800"),
    current_price: Decimal = Decimal("2850"),
    stop_price: Decimal = Decimal("2710"),
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


def _featured_df_for_exit(
    close: float = 2850.0,
    dma_10: float = 2840.0,
    dma_200: float = 2500.0,
    n_rows: int = 5,
) -> pd.DataFrame:
    """Create a featured DataFrame for exit testing."""
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


class TestExitRules:
    def test_stop_hit_exit(self) -> None:
        pos = _swing_position(stop_price=Decimal("2710"))
        # Close at 2700 → below stop
        data = {"RELIANCE": _featured_df_for_exit(close=2700.0)}
        decisions = evaluate_exits([pos], data, _regime())
        assert len(decisions) == 1
        assert decisions[0].decision == "exit_full"
        assert decisions[0].exit_reason == "stop_hit"
        assert decisions[0].order_intent is not None

    def test_partial_profit_2r(self) -> None:
        # Entry 2800, stop 2710, risk = 90. +2R = 2800 + 180 = 2980
        pos = _swing_position(
            entry_price=Decimal("2800"),
            stop_price=Decimal("2710"),
            quantity=10,
        )
        data = {"RELIANCE": _featured_df_for_exit(close=2990.0, dma_10=2985.0)}
        decisions = evaluate_exits([pos], data, _regime())
        assert decisions[0].decision == "exit_partial"
        assert decisions[0].exit_reason == "partial_profit_2R"
        assert decisions[0].order_intent is not None
        assert decisions[0].order_intent.quantity == 5  # 50% of 10

    def test_trail_stop_10dma(self) -> None:
        # Close below 10-DMA
        pos = _swing_position(
            entry_price=Decimal("2800"),
            stop_price=Decimal("2710"),
        )
        data = {"RELIANCE": _featured_df_for_exit(close=2770.0, dma_10=2790.0)}
        decisions = evaluate_exits([pos], data, _regime())
        assert decisions[0].decision == "exit_full"
        assert decisions[0].exit_reason == "trail_stop_10dma"

    def test_hold_no_trigger(self) -> None:
        pos = _swing_position()
        # Normal price, above stop, below 2R, above 10-DMA
        data = {"RELIANCE": _featured_df_for_exit(close=2850.0, dma_10=2840.0)}
        decisions = evaluate_exits([pos], data, _regime())
        assert decisions[0].decision == "hold"

    def test_core_200dma_break_1_day_hold(self) -> None:
        # Core position, below 200-DMA for only 1 day out of 3
        pos = _core_position()
        base = {"volume": 3_000_000, "dma_200": 4000}
        rows = [
            {"date": date(2025, 12, 10), "open": 4050,
             "high": 4060, "low": 4030, "close": 4050,
             "dma_10": 4040, **base},
            {"date": date(2025, 12, 11), "open": 4040,
             "high": 4050, "low": 4020, "close": 4020,
             "dma_10": 4035, **base},
            {"date": date(2025, 12, 12), "open": 3990,
             "high": 4010, "low": 3980, "close": 3990,
             "dma_10": 4030, **base},
        ]
        data = {"TCS": pd.DataFrame(rows)}
        decisions = evaluate_exits([pos], data, _regime())
        assert decisions[0].decision == "hold"

    def test_core_200dma_break_3_days_exit(self) -> None:
        # Core position, below 200-DMA for 3 consecutive sessions
        pos = _core_position()
        base = {"volume": 3_000_000, "dma_200": 4000}
        rows = [
            {"date": date(2025, 12, 10), "open": 3990,
             "high": 3995, "low": 3970, "close": 3980,
             "dma_10": 4030, **base},
            {"date": date(2025, 12, 11), "open": 3975,
             "high": 3985, "low": 3960, "close": 3970,
             "dma_10": 4025, **base},
            {"date": date(2025, 12, 12), "open": 3960,
             "high": 3975, "low": 3950, "close": 3960,
             "dma_10": 4020, **base},
        ]
        data = {"TCS": pd.DataFrame(rows)}
        decisions = evaluate_exits([pos], data, _regime())
        assert decisions[0].decision == "exit_full"
        assert decisions[0].exit_reason == "200dma_break_3_sessions"


# --- Position sizer tests ---


class TestPositionSizer:
    def test_green_regime_sizing(self) -> None:
        qty = calculate_position_size(
            equity=Decimal("10000000"),
            risk_per_trade_pct=Decimal("0.50"),
            risk_per_share=Decimal("200"),
            regime=_regime(RegimeClass.GREEN),
            layer=PortfolioLayer.SWING,
        )
        # 10_000_000 * 0.005 / 200 = 250
        assert qty == 250

    def test_mixed_regime_half_sizing(self) -> None:
        qty = calculate_position_size(
            equity=Decimal("10000000"),
            risk_per_trade_pct=Decimal("0.50"),
            risk_per_share=Decimal("200"),
            regime=_regime(RegimeClass.MIXED),
            layer=PortfolioLayer.SWING,
        )
        # 10_000_000 * 0.005 / 200 * 0.5 = 125
        assert qty == 125

    def test_stressed_regime_zero(self) -> None:
        qty = calculate_position_size(
            equity=Decimal("10000000"),
            risk_per_trade_pct=Decimal("0.50"),
            risk_per_share=Decimal("200"),
            regime=_regime(RegimeClass.STRESSED),
            layer=PortfolioLayer.SWING,
        )
        assert qty == 0

    def test_small_equity_expensive_stock(self) -> None:
        qty = calculate_position_size(
            equity=Decimal("50000"),
            risk_per_trade_pct=Decimal("0.50"),
            risk_per_share=Decimal("500"),
            regime=_regime(RegimeClass.GREEN),
            layer=PortfolioLayer.SWING,
        )
        # 50_000 * 0.005 / 500 = 0.5 → 0
        assert qty == 0

    def test_zero_risk_per_share(self) -> None:
        qty = calculate_position_size(
            equity=Decimal("1000000"),
            risk_per_trade_pct=Decimal("0.50"),
            risk_per_share=Decimal("0"),
            regime=_regime(RegimeClass.GREEN),
            layer=PortfolioLayer.SWING,
        )
        assert qty == 0
