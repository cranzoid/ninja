"""Feature builder — enriches raw OHLCV data with technical indicators."""

from __future__ import annotations

import pandas as pd

from .indicators import atr, dma, rolling_avg_volume, rolling_high, volume_ratio


def build_features(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """
    Take raw OHLCV DataFrame and append all indicator and boolean columns.

    Input columns: date, open, high, low, close, volume
    Added indicator columns: dma_200, dma_50, dma_10, atr_14,
        high_20d, avg_volume_20d, volume_ratio_20d
    Added boolean columns: above_200dma, above_50dma, dma_50_above_200,
        close_above_20d_high, volume_sufficient, extended_above_50dma
    """
    df = ohlcv.copy()

    # Moving averages
    df["dma_200"] = dma(df["close"], 200)
    df["dma_50"] = dma(df["close"], 50)
    df["dma_10"] = dma(df["close"], 10)

    # ATR
    df["atr_14"] = atr(df["high"], df["low"], df["close"], 14)

    # Rolling stats
    df["high_20d"] = rolling_high(df["close"], 20)
    df["avg_volume_20d"] = rolling_avg_volume(df["volume"], 20)
    df["volume_ratio_20d"] = volume_ratio(df["volume"], 20)

    # Boolean columns for rule engine
    df["above_200dma"] = df["close"] > df["dma_200"]
    df["above_50dma"] = df["close"] > df["dma_50"]
    df["dma_50_above_200"] = df["dma_50"] > df["dma_200"]

    # Shift high_20d by 1 to avoid look-ahead bias
    df["close_above_20d_high"] = df["close"] > df["high_20d"].shift(1)

    # Volume >= 1.2x average
    df["volume_sufficient"] = df["volume_ratio_20d"] >= 1.2

    # Extended > 12% above 50-DMA (charter §6.4)
    df["extended_above_50dma"] = ((df["close"] - df["dma_50"]) / df["dma_50"]) > 0.12

    return df
