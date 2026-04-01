"""Technical indicator calculations — pure functions on pandas Series."""

from __future__ import annotations

import pandas as pd


def dma(series: pd.Series, period: int) -> pd.Series:
    """Simple (daily) moving average over `period` days."""
    return series.rolling(window=period, min_periods=period).mean()


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Average True Range over `period` days."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.rolling(window=period, min_periods=period).mean()


def rolling_high(series: pd.Series, period: int = 20) -> pd.Series:
    """Rolling maximum over `period` days."""
    return series.rolling(window=period, min_periods=period).max()


def rolling_avg_volume(volume: pd.Series, period: int = 20) -> pd.Series:
    """Rolling average volume over `period` days."""
    return volume.rolling(window=period, min_periods=period).mean()


def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """Current volume divided by rolling average volume."""
    avg = rolling_avg_volume(volume, period)
    return volume / avg
