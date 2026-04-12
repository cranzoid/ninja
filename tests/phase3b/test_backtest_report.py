"""Tests for BacktestReport contract — Phase 3B.

Validates construction, immutability, and core metric relationships.
No network calls, no existing tests modified.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from packages.contracts.backtest_report import BacktestReport
from packages.contracts.enums import Mode, RegimeClass
from packages.contracts.eod_report import EODRunReport
from packages.contracts.reconciliation import ReconciliationReport
from packages.contracts.regime_state import RegimeState
from packages.contracts.risk import PortfolioRisk

# ---------------------------------------------------------------------------
# Minimal stub helpers
# ---------------------------------------------------------------------------


def _stub_regime() -> RegimeState:
    return RegimeState(
        assessed_at=datetime.now(UTC),
        regime_class=RegimeClass.GREEN,
        nifty50_trend="bullish",
        breadth_above_50dma_pct=Decimal("70.0"),
        breadth_above_200dma_pct=Decimal("65.0"),
        vix_level=None,
        vix_state="normal",
        gap_frequency_5d=Decimal("0"),
        sector_concentration_score=Decimal("0.4"),
        correlation_state="normal",
        sizing_multiplier=Decimal("1.0"),
        rationale="Test regime",
    )


def _stub_portfolio_risk() -> PortfolioRisk:
    return PortfolioRisk(
        total_equity=Decimal("50000"),
        total_open_risk=Decimal("750"),
        open_risk_pct=Decimal("1.5"),
        position_count=2,
        sector_exposure={},
        largest_position_pct=Decimal("8.0"),
        is_within_limits=True,
        limit_breaches=[],
    )


def _stub_reconciliation(trading_date: date) -> ReconciliationReport:
    return ReconciliationReport(
        reconciled_at=datetime.now(UTC),
        target_date=trading_date,
        positions_match=True,
        orders_match=True,
        position_mismatches=[],
        order_mismatches=[],
        unmatched_intents=[],
        orphan_fills=[],
        is_clean=True,
    )


def _stub_eod_report(trading_date: date) -> EODRunReport:
    return EODRunReport(
        run_id="test-run-id",
        trading_date=trading_date,
        mode=Mode.PAPER,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        regime=_stub_regime(),
        candidates_scanned=10,
        swing_candidates_passing=2,
        core_candidates_passing=1,
        entries_approved=1,
        entries_rejected=1,
        exits_triggered=0,
        orders_filled=0,
        portfolio_risk=_stub_portfolio_risk(),
        reconciliation=_stub_reconciliation(trading_date),
        errors=[],
        is_successful=True,
    )


def _make_backtest_report(**overrides: object) -> BacktestReport:
    """Build a minimal valid BacktestReport with sensible defaults."""
    td = date(2023, 1, 3)
    defaults: dict[str, object] = {
        "run_id": "test-run-123",
        "generated_at": datetime.now(UTC),
        "start_date": date(2023, 1, 1),
        "end_date": date(2023, 12, 31),
        "initial_equity": Decimal("50000"),
        "final_equity": Decimal("55000"),
        "total_return_pct": Decimal("10.0"),
        "nifty_return_pct": Decimal("7.0"),
        "alpha_pct": Decimal("3.0"),
        "max_drawdown_pct": Decimal("5.0"),
        "max_drawdown_start": date(2023, 3, 1),
        "max_drawdown_end": date(2023, 3, 15),
        "total_trades": 20,
        "winning_trades": 14,
        "losing_trades": 6,
        "win_rate_pct": Decimal("70.0"),
        "avg_win_pct": Decimal("3.2"),
        "avg_loss_pct": Decimal("1.5"),
        "profit_factor": Decimal("2.1"),
        "trades_in_green_regime": 15,
        "trades_in_mixed_regime": 5,
        "trades_in_stressed_regime": 0,
        "trading_days_run": 250,
        "days_with_errors": 0,
        "all_reconciliations_clean": True,
        "equity_curve": [(td, Decimal("50500"))],
        "daily_reports": [_stub_eod_report(td)],
    }
    defaults.update(overrides)
    return BacktestReport(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# test_backtest_report_construction
# ---------------------------------------------------------------------------


def test_backtest_report_construction() -> None:
    """BacktestReport constructs without error from valid data."""
    report = _make_backtest_report()

    assert report.run_id == "test-run-123"
    assert report.initial_equity == Decimal("50000")
    assert report.final_equity == Decimal("55000")
    assert report.alpha_pct == Decimal("3.0")


# ---------------------------------------------------------------------------
# test_backtest_report_is_frozen
# ---------------------------------------------------------------------------


def test_backtest_report_is_frozen() -> None:
    """BacktestReport must be immutable — attribute assignment must raise."""
    report = _make_backtest_report()

    with pytest.raises((TypeError, AttributeError, ValidationError)):
        report.total_return_pct = Decimal("99.0")  # type: ignore[misc]


# ---------------------------------------------------------------------------
# test_alpha_equals_total_minus_nifty
# ---------------------------------------------------------------------------


def test_alpha_equals_total_minus_nifty() -> None:
    """Verify the caller correctly sets alpha = total_return - nifty_return."""
    total = Decimal("12.5")
    nifty = Decimal("8.0")
    alpha = total - nifty  # 4.5

    report = _make_backtest_report(
        total_return_pct=total,
        nifty_return_pct=nifty,
        alpha_pct=alpha,
    )

    assert report.alpha_pct == Decimal("4.5"), (
        "alpha_pct must equal total_return_pct - nifty_return_pct"
    )


# ---------------------------------------------------------------------------
# test_win_rate_calculation
# ---------------------------------------------------------------------------


def test_win_rate_calculation() -> None:
    """win_rate_pct must be consistent with winning_trades / total_trades * 100."""
    total = 20
    wins = 14
    expected_rate = Decimal(str(wins / total * 100)).quantize(Decimal("0.01"))

    report = _make_backtest_report(
        total_trades=total,
        winning_trades=wins,
        losing_trades=total - wins,
        win_rate_pct=expected_rate,
    )

    computed = (
        Decimal(str(report.winning_trades))
        / Decimal(str(report.total_trades))
        * 100
    ).quantize(Decimal("0.01"))
    assert computed == report.win_rate_pct, (
        "win_rate_pct must equal winning_trades / total_trades * 100"
    )


# ---------------------------------------------------------------------------
# test_regime_breakdown_sums_to_total_trades
# ---------------------------------------------------------------------------


def test_regime_breakdown_sums_to_total_trades() -> None:
    """Sum of regime trade counts must equal total_trades."""
    green = 15
    mixed = 4
    stressed = 1
    total = green + mixed + stressed

    report = _make_backtest_report(
        total_trades=total,
        winning_trades=total,
        losing_trades=0,
        win_rate_pct=Decimal("100"),
        trades_in_green_regime=green,
        trades_in_mixed_regime=mixed,
        trades_in_stressed_regime=stressed,
    )

    regime_sum = (
        report.trades_in_green_regime
        + report.trades_in_mixed_regime
        + report.trades_in_stressed_regime
    )
    assert regime_sum == report.total_trades, (
        "Regime trade breakdown must sum to total_trades"
    )


# ---------------------------------------------------------------------------
# test_equity_curve_is_list_of_date_decimal_tuples
# ---------------------------------------------------------------------------


def test_equity_curve_is_list_of_date_decimal_tuples() -> None:
    """equity_curve must be a list of (date, Decimal) tuples."""
    curve = [
        (date(2023, 1, 2), Decimal("50000")),
        (date(2023, 1, 3), Decimal("50500")),
        (date(2023, 1, 4), Decimal("51000")),
    ]
    report = _make_backtest_report(equity_curve=curve)

    assert len(report.equity_curve) == 3
    first_date, first_equity = report.equity_curve[0]
    assert isinstance(first_date, date)
    assert isinstance(first_equity, Decimal)
