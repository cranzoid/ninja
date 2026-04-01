"""Tests for the regime engine."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd

from packages.contracts.enums import RegimeClass
from services.regime_engine.assessor import assess_regime


def _make_nifty_data(
    close: float = 22000.0,
    dma_200: float = 21000.0,
    n_rows: int = 250,
) -> pd.DataFrame:
    """Create featured NIFTY 50 data."""
    from services.feature_engine.builder import build_features

    dates = []
    d = date(2025, 1, 1)
    while len(dates) < n_rows:
        if d.weekday() < 5:
            dates.append(d)
        d += timedelta(days=1)

    # Simple uptrend
    closes = [close - (n_rows - i) * 5 for i in range(n_rows)]
    df = pd.DataFrame({
        "date": dates,
        "open": [c - 50 for c in closes],
        "high": [c + 100 for c in closes],
        "low": [c - 100 for c in closes],
        "close": closes,
        "volume": [100_000_000] * n_rows,
    })
    return build_features(df)


def _make_bearish_nifty() -> pd.DataFrame:
    """NIFTY in downtrend — close well below 200-DMA."""
    dates = []
    d = date(2025, 1, 1)
    while len(dates) < 250:
        if d.weekday() < 5:
            dates.append(d)
        d += timedelta(days=1)

    # Downtrend: start high, end low
    closes = [22000 - i * 20 for i in range(250)]
    df = pd.DataFrame({
        "date": dates,
        "open": [c + 50 for c in closes],
        "high": [c + 100 for c in closes],
        "low": [c - 100 for c in closes],
        "close": closes,
        "volume": [100_000_000] * 250,
    })
    from services.feature_engine.builder import build_features
    return build_features(df)


def _make_universe_data(
    n_symbols: int = 10,
    pct_above_50dma: float = 0.8,
) -> dict[str, pd.DataFrame]:
    """Create simplified universe data with controlled breadth."""
    from services.feature_engine.builder import build_features

    data = {}
    dates = []
    d = date(2025, 1, 1)
    while len(dates) < 250:
        if d.weekday() < 5:
            dates.append(d)
        d += timedelta(days=1)

    for i in range(n_symbols):
        # Some in uptrend (above 50-DMA), some in downtrend
        if i < int(n_symbols * pct_above_50dma):
            closes = [1000 + j * 2 for j in range(250)]  # uptrend
        else:
            closes = [1000 - j * 2 for j in range(250)]  # downtrend

        df = pd.DataFrame({
            "date": dates,
            "open": [c - 5 for c in closes],
            "high": [c + 10 for c in closes],
            "low": [c - 10 for c in closes],
            "close": closes,
            "volume": [5_000_000] * 250,
        })
        data[f"SYM{i}"] = build_features(df)

    return data


class TestRegimeAssessor:
    def test_green_regime_bullish_market(self) -> None:
        nifty = _make_nifty_data()
        universe = _make_universe_data(n_symbols=10, pct_above_50dma=0.8)
        result = assess_regime(nifty, universe, vix_level=Decimal("13.0"))
        assert result.regime_class == RegimeClass.GREEN
        assert result.sizing_multiplier == Decimal("1.0")
        assert result.nifty50_trend == "bullish"

    def test_stressed_regime_bearish_market(self) -> None:
        nifty = _make_bearish_nifty()
        universe = _make_universe_data(n_symbols=10, pct_above_50dma=0.2)
        result = assess_regime(nifty, universe, vix_level=Decimal("30.0"))
        assert result.regime_class == RegimeClass.STRESSED
        assert result.sizing_multiplier == Decimal("0.0")

    def test_mixed_regime(self) -> None:
        nifty = _make_nifty_data()
        # Mixed breadth — not clearly green or stressed
        universe = _make_universe_data(n_symbols=10, pct_above_50dma=0.5)
        result = assess_regime(nifty, universe, vix_level=Decimal("22.0"))
        assert result.regime_class == RegimeClass.MIXED
        assert result.sizing_multiplier == Decimal("0.5")

    def test_missing_vix_uses_fallback(self) -> None:
        nifty = _make_nifty_data()
        universe = _make_universe_data(n_symbols=10, pct_above_50dma=0.8)
        result = assess_regime(nifty, universe, vix_level=None)
        # Should still produce a valid regime
        valid = {RegimeClass.GREEN, RegimeClass.MIXED, RegimeClass.STRESSED}
        assert result.regime_class in valid
        assert result.vix_state in {"low", "normal", "elevated", "extreme"}

    def test_regime_state_contract_valid(self) -> None:
        nifty = _make_nifty_data()
        universe = _make_universe_data()
        result = assess_regime(nifty, universe, vix_level=Decimal("15.0"))
        # Verify it's a valid RegimeState contract
        assert result.assessed_at is not None
        assert result.rationale
        assert 0 <= float(result.breadth_above_50dma_pct) <= 100
