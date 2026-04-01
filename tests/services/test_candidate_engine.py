"""Tests for the candidate engine."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd

from packages.contracts.candidates import SwingCandidate
from packages.contracts.enums import RegimeClass
from packages.contracts.regime_state import RegimeState
from services.candidate_engine.core_scanner import scan_core_candidates
from services.candidate_engine.ranker import rank_swing_candidates
from services.candidate_engine.swing_scanner import scan_swing_candidates


def _green_regime() -> RegimeState:
    return RegimeState(
        assessed_at=datetime.now(UTC),
        regime_class=RegimeClass.GREEN,
        nifty50_trend="bullish",
        breadth_above_50dma_pct=Decimal("72.5"),
        breadth_above_200dma_pct=Decimal("81.0"),
        vix_level=Decimal("14.2"),
        vix_state="low",
        gap_frequency_5d=Decimal("0.8"),
        sector_concentration_score=Decimal("0.35"),
        correlation_state="normal",
        sizing_multiplier=Decimal("1.0"),
        rationale="Bullish market.",
    )


def _stressed_regime() -> RegimeState:
    return RegimeState(
        assessed_at=datetime.now(UTC),
        regime_class=RegimeClass.STRESSED,
        nifty50_trend="bearish",
        breadth_above_50dma_pct=Decimal("28.0"),
        breadth_above_200dma_pct=Decimal("45.0"),
        vix_level=Decimal("32.0"),
        vix_state="extreme",
        gap_frequency_5d=Decimal("5.0"),
        sector_concentration_score=Decimal("0.72"),
        correlation_state="expanded",
        sizing_multiplier=Decimal("0.0"),
        rationale="Bearish market.",
    )


def _mixed_regime() -> RegimeState:
    return RegimeState(
        assessed_at=datetime.now(UTC),
        regime_class=RegimeClass.MIXED,
        nifty50_trend="neutral",
        breadth_above_50dma_pct=Decimal("50.0"),
        breadth_above_200dma_pct=Decimal("60.0"),
        vix_level=Decimal("18.0"),
        vix_state="normal",
        gap_frequency_5d=Decimal("2.0"),
        sector_concentration_score=Decimal("0.50"),
        correlation_state="normal",
        sizing_multiplier=Decimal("0.5"),
        rationale="Mixed signals.",
    )


def _make_featured_df(
    close: float = 2800.0,
    dma_50: float = 2700.0,
    dma_200: float = 2500.0,
    dma_10: float = 2780.0,
    atr_14: float = 45.0,
    high_20d: float = 2750.0,
    volume_ratio_20d: float = 1.5,
    above_50dma: bool = True,
    above_200dma: bool = True,
    dma_50_above_200: bool = True,
    close_above_20d_high: bool = True,
    volume_sufficient: bool = True,
    extended_above_50dma: bool = False,
) -> pd.DataFrame:
    """Create a one-row featured DataFrame for testing."""
    return pd.DataFrame([{
        "date": date(2025, 12, 15),
        "open": close - 10,
        "high": close + 20,
        "low": close - 20,
        "close": close,
        "volume": 15_000_000,
        "dma_200": dma_200,
        "dma_50": dma_50,
        "dma_10": dma_10,
        "atr_14": atr_14,
        "high_20d": high_20d,
        "avg_volume_20d": 10_000_000,
        "volume_ratio_20d": volume_ratio_20d,
        "above_200dma": above_200dma,
        "above_50dma": above_50dma,
        "dma_50_above_200": dma_50_above_200,
        "close_above_20d_high": close_above_20d_high,
        "volume_sufficient": volume_sufficient,
        "extended_above_50dma": extended_above_50dma,
    }])


class TestSwingScanner:
    def test_passing_candidate(self) -> None:
        data = {"RELIANCE": _make_featured_df()}
        result = scan_swing_candidates(data, _green_regime())
        assert len(result) == 1
        assert result[0].passes_all_entry_conditions is True
        assert result[0].failed_conditions == []
        assert result[0].symbol == "RELIANCE"

    def test_fails_volume(self) -> None:
        data = {"TCS": _make_featured_df(volume_sufficient=False)}
        result = scan_swing_candidates(data, _green_regime())
        assert len(result) == 1
        assert result[0].passes_all_entry_conditions is False
        assert "volume_insufficient" in result[0].failed_conditions

    def test_fails_dma_alignment(self) -> None:
        data = {"INFY": _make_featured_df(dma_50_above_200=False)}
        result = scan_swing_candidates(data, _green_regime())
        assert result[0].passes_all_entry_conditions is False
        assert "50dma_below_200dma" in result[0].failed_conditions

    def test_stressed_regime_blocks_all(self) -> None:
        data = {"RELIANCE": _make_featured_df()}
        result = scan_swing_candidates(data, _stressed_regime())
        assert len(result) == 1
        assert result[0].passes_all_entry_conditions is False
        assert "regime_stressed" in result[0].failed_conditions

    def test_mixed_regime_allows_candidates(self) -> None:
        data = {"RELIANCE": _make_featured_df()}
        result = scan_swing_candidates(data, _mixed_regime())
        assert len(result) == 1
        assert result[0].passes_all_entry_conditions is True

    def test_stop_price_is_2x_atr_below_entry(self) -> None:
        data = {"RELIANCE": _make_featured_df(close=2800.0, atr_14=45.0)}
        result = scan_swing_candidates(data, _green_regime())
        expected_stop = Decimal("2800.00") - 2 * Decimal("45.0")
        assert result[0].stop_price == expected_stop

    def test_multiple_symbols(self) -> None:
        data = {
            "RELIANCE": _make_featured_df(),
            "TCS": _make_featured_df(volume_sufficient=False),
            "INFY": _make_featured_df(above_50dma=False),
        }
        result = scan_swing_candidates(data, _green_regime())
        assert len(result) == 3
        passing = [c for c in result if c.passes_all_entry_conditions]
        assert len(passing) == 1
        assert passing[0].symbol == "RELIANCE"


class TestCoreScanner:
    def test_passing_candidate(self) -> None:
        data = {"RELIANCE": _make_featured_df()}
        result = scan_core_candidates(data, _green_regime())
        assert len(result) == 1
        assert result[0].passes_entry_conditions is True

    def test_fails_below_200dma(self) -> None:
        df = _make_featured_df(
            above_200dma=False, close=2400.0, dma_200=2500.0,
        )
        data = {"TCS": df}
        result = scan_core_candidates(data, _green_regime())
        assert result[0].passes_entry_conditions is False
        assert "below_200dma" in result[0].failed_conditions

    def test_fails_extended(self) -> None:
        data = {"INFY": _make_featured_df(extended_above_50dma=True)}
        result = scan_core_candidates(data, _green_regime())
        assert result[0].passes_entry_conditions is False
        assert "extended_above_50dma" in result[0].failed_conditions

    def test_stressed_regime_blocks(self) -> None:
        data = {"RELIANCE": _make_featured_df()}
        result = scan_core_candidates(data, _stressed_regime())
        assert result[0].passes_entry_conditions is False
        assert "regime_stressed" in result[0].failed_conditions


class TestRanker:
    def test_limits_output(self) -> None:
        candidates = [
            SwingCandidate(
                symbol=f"SYM{i}",
                scan_date=date(2025, 12, 15),
                close=Decimal("2800"),
                entry_price_estimate=Decimal("2800"),
                stop_price=Decimal("2710"),
                risk_per_share=Decimal("90"),
                volume_ratio=Decimal(str(1.5 + i * 0.1)),
                atr_14=Decimal("45"),
                regime_at_scan=RegimeClass.GREEN,
                passes_all_entry_conditions=True,
                failed_conditions=[],
            )
            for i in range(5)
        ]
        ranked = rank_swing_candidates(candidates, max_entries=2)
        assert len(ranked) == 2

    def test_ranks_by_volume_ratio(self) -> None:
        high_vol = SwingCandidate(
            symbol="HIGH_VOL",
            scan_date=date(2025, 12, 15),
            close=Decimal("2800"),
            entry_price_estimate=Decimal("2800"),
            stop_price=Decimal("2710"),
            risk_per_share=Decimal("90"),
            volume_ratio=Decimal("2.5"),
            atr_14=Decimal("45"),
            regime_at_scan=RegimeClass.GREEN,
            passes_all_entry_conditions=True,
            failed_conditions=[],
        )
        low_vol = SwingCandidate(
            symbol="LOW_VOL",
            scan_date=date(2025, 12, 15),
            close=Decimal("2800"),
            entry_price_estimate=Decimal("2800"),
            stop_price=Decimal("2710"),
            risk_per_share=Decimal("90"),
            volume_ratio=Decimal("1.3"),
            atr_14=Decimal("45"),
            regime_at_scan=RegimeClass.GREEN,
            passes_all_entry_conditions=True,
            failed_conditions=[],
        )
        ranked = rank_swing_candidates([low_vol, high_vol], max_entries=2)
        assert ranked[0].symbol == "HIGH_VOL"

    def test_excludes_failing_candidates(self) -> None:
        passing = SwingCandidate(
            symbol="PASS",
            scan_date=date(2025, 12, 15),
            close=Decimal("2800"),
            entry_price_estimate=Decimal("2800"),
            stop_price=Decimal("2710"),
            risk_per_share=Decimal("90"),
            volume_ratio=Decimal("1.5"),
            atr_14=Decimal("45"),
            regime_at_scan=RegimeClass.GREEN,
            passes_all_entry_conditions=True,
            failed_conditions=[],
        )
        failing = SwingCandidate(
            symbol="FAIL",
            scan_date=date(2025, 12, 15),
            close=Decimal("2800"),
            entry_price_estimate=Decimal("2800"),
            stop_price=Decimal("2710"),
            risk_per_share=Decimal("90"),
            volume_ratio=Decimal("3.0"),
            atr_14=Decimal("45"),
            regime_at_scan=RegimeClass.GREEN,
            passes_all_entry_conditions=False,
            failed_conditions=["volume_insufficient"],
        )
        ranked = rank_swing_candidates([failing, passing], max_entries=5)
        assert len(ranked) == 1
        assert ranked[0].symbol == "PASS"
