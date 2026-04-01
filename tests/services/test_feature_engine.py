"""Tests for the feature engine."""

from __future__ import annotations

import pandas as pd
import pytest

from services.feature_engine.builder import build_features
from services.feature_engine.indicators import (
    atr,
    dma,
    rolling_avg_volume,
    rolling_high,
    volume_ratio,
)


def _make_ohlcv(n: int = 30, base_price: float = 100.0) -> pd.DataFrame:
    """Create a simple OHLCV DataFrame with known values."""
    from datetime import date, timedelta

    dates = [date(2025, 1, 2) + timedelta(days=i) for i in range(n)]
    # Linear uptrend for predictable indicator values
    closes = [base_price + i * 0.5 for i in range(n)]
    opens = [c - 0.2 for c in closes]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    volumes = [1_000_000 + i * 10_000 for i in range(n)]

    return pd.DataFrame({
        "date": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


class TestIndicators:
    def test_dma_basic(self) -> None:
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = dma(series, 3)
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == pytest.approx(2.0)
        assert result.iloc[3] == pytest.approx(3.0)
        assert result.iloc[4] == pytest.approx(4.0)

    def test_dma_not_enough_data(self) -> None:
        series = pd.Series([1.0, 2.0])
        result = dma(series, 5)
        assert all(pd.isna(result))

    def test_atr_basic(self) -> None:
        high = pd.Series([12.0, 13.0, 14.0, 13.5, 14.5] * 4)
        low = pd.Series([10.0, 11.0, 12.0, 11.5, 12.5] * 4)
        close = pd.Series([11.0, 12.0, 13.0, 12.5, 13.5] * 4)
        result = atr(high, low, close, period=14)
        # First 13 values should be NaN, 14th should be computed
        assert pd.isna(result.iloc[0])
        assert pd.notna(result.iloc[13])
        assert result.iloc[13] > 0

    def test_rolling_high(self) -> None:
        series = pd.Series(list(range(1, 26)))
        result = rolling_high(series, 5)
        assert pd.isna(result.iloc[3])
        assert result.iloc[4] == 5.0
        assert result.iloc[9] == 10.0

    def test_rolling_avg_volume(self) -> None:
        vol = pd.Series([100] * 20 + [200])
        result = rolling_avg_volume(vol, 20)
        assert result.iloc[19] == pytest.approx(100.0)

    def test_volume_ratio(self) -> None:
        vol = pd.Series([100] * 21 + [200])
        result = volume_ratio(vol, 20)
        # avg of [100]*20 = 100, then 200/avg([100]*19 + [200]) = 200/105 ≈ 1.905
        # For exact 2.0: use index 20 where rolling avg is pure 100s
        assert result.iloc[20] == pytest.approx(1.0)  # 100 / avg(100s) = 1.0
        assert result.iloc[21] > 1.5  # 200 / avg with mostly 100s


class TestBuildFeatures:
    def test_adds_all_indicator_columns(self) -> None:
        df = _make_ohlcv(250)
        featured = build_features(df)

        expected_indicators = [
            "dma_200", "dma_50", "dma_10", "atr_14",
            "high_20d", "avg_volume_20d", "volume_ratio_20d",
        ]
        for col in expected_indicators:
            assert col in featured.columns, f"Missing column: {col}"

    def test_adds_all_boolean_columns(self) -> None:
        df = _make_ohlcv(250)
        featured = build_features(df)

        expected_booleans = [
            "above_200dma", "above_50dma", "dma_50_above_200",
            "close_above_20d_high", "volume_sufficient",
            "extended_above_50dma",
        ]
        for col in expected_booleans:
            assert col in featured.columns, f"Missing column: {col}"

    def test_boolean_correctness_above_200dma(self) -> None:
        df = _make_ohlcv(250)
        featured = build_features(df)
        # In uptrend, last rows should be above 200-DMA
        last_row = featured.iloc[-1]
        if pd.notna(last_row["dma_200"]):
            expected = last_row["close"] > last_row["dma_200"]
            assert last_row["above_200dma"] == expected

    def test_not_enough_for_200dma(self) -> None:
        df = _make_ohlcv(50)
        featured = build_features(df)
        # All dma_200 values should be NaN
        assert featured["dma_200"].isna().all()

    def test_extended_above_50dma_flag(self) -> None:
        # Create data where close is 15% above 50-DMA
        df = _make_ohlcv(60, base_price=100.0)
        # Override last close to be very high
        df.loc[df.index[-1], "close"] = 200.0
        featured = build_features(df)
        last = featured.iloc[-1]
        if pd.notna(last["dma_50"]):
            pct = (last["close"] - last["dma_50"]) / last["dma_50"]
            assert last["extended_above_50dma"] == (pct > 0.12)

    def test_preserves_original_columns(self) -> None:
        df = _make_ohlcv(30)
        featured = build_features(df)
        for col in ["date", "open", "high", "low", "close", "volume"]:
            assert col in featured.columns
