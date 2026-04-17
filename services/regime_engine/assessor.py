"""Regime assessor — classifies market regime per charter §6.7."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

import numpy as np
import pandas as pd

from packages.contracts.enums import RegimeClass
from packages.contracts.regime_state import RegimeState

logger = logging.getLogger(__name__)


def assess_regime(
    nifty50_data: pd.DataFrame,
    universe_data: dict[str, pd.DataFrame],
    vix_level: Decimal | None,
) -> RegimeState:
    """
    Assess market regime from NIFTY 50 data, universe breadth, and VIX.

    Implements charter §6.7 regime stack:
    - NIFTY 50 trend (bullish/bearish/neutral vs 200-DMA)
    - Breadth (% above 50-DMA and 200-DMA)
    - VIX state (low/normal/elevated/extreme)
    - Gap frequency (>1% gaps in last 5 sessions)
    - Sector concentration (std of returns)
    - Correlation (average pairwise correlation)
    """
    logger.info(
        "Regime inputs: nifty_rows=%d universe_symbols=%d vix_level=%s",
        len(nifty50_data),
        len(universe_data),
        vix_level,
    )

    # 1. NIFTY 50 trend
    nifty_trend = _assess_nifty_trend(nifty50_data)

    # 2. Breadth
    above_50dma_pct, above_200dma_pct = _assess_breadth(universe_data)

    # 3. VIX state
    vix_state = _classify_vix(vix_level)
    effective_vix = vix_level
    if vix_level is None and not nifty50_data.empty:
        # Fallback: use realized volatility of NIFTY 50 as proxy
        returns = nifty50_data["close"].pct_change().dropna()
        if len(returns) >= 20:
            realized_vol = float(returns.tail(20).std()) * np.sqrt(252) * 100
            effective_vix = Decimal(str(round(realized_vol, 1)))
            vix_state = _classify_vix(effective_vix)

    # 4. Gap frequency
    gap_freq = _count_gaps(universe_data)

    # 5. Sector concentration (simplified: std of per-symbol returns)
    concentration = _sector_concentration(universe_data)

    # 6. Correlation state
    corr_state = _correlation_state(universe_data)

    # Classification logic
    regime_class = _classify_regime(
        nifty_trend, above_50dma_pct, vix_state, gap_freq
    )

    sizing_map = {
        RegimeClass.GREEN: Decimal("1.0"),
        RegimeClass.MIXED: Decimal("0.5"),
        RegimeClass.STRESSED: Decimal("0.0"),
    }

    rationale = _build_rationale(
        nifty_trend, above_50dma_pct, vix_state, gap_freq
    )

    return RegimeState(
        assessed_at=datetime.now(UTC),
        regime_class=regime_class,
        nifty50_trend=nifty_trend,
        breadth_above_50dma_pct=above_50dma_pct,
        breadth_above_200dma_pct=above_200dma_pct,
        vix_level=effective_vix,
        vix_state=vix_state,
        gap_frequency_5d=gap_freq,
        sector_concentration_score=concentration,
        correlation_state=corr_state,
        sizing_multiplier=sizing_map[regime_class],
        rationale=rationale,
    )


def _assess_nifty_trend(
    df: pd.DataFrame,
) -> Literal["bullish", "bearish", "neutral"]:
    """Classify NIFTY 50 trend relative to 200-DMA."""
    if df.empty or "dma_200" not in df.columns:
        return "neutral"

    latest = df.iloc[-1]
    if pd.isna(latest.get("dma_200")):
        return "neutral"

    close = float(latest["close"])
    dma_200 = float(latest["dma_200"])

    if dma_200 == 0:
        return "neutral"

    pct_from_dma = (close - dma_200) / dma_200

    if pct_from_dma > 0.01:
        return "bullish"
    elif pct_from_dma < -0.01:
        return "bearish"
    return "neutral"


def _assess_breadth(
    universe_data: dict[str, pd.DataFrame],
) -> tuple[Decimal, Decimal]:
    """Calculate % of universe above 50-DMA and 200-DMA."""
    if not universe_data:
        return Decimal("50.0"), Decimal("50.0")

    above_50 = 0
    above_200 = 0
    total = 0

    for df in universe_data.values():
        if df.empty:
            continue
        latest = df.iloc[-1]
        if pd.notna(latest.get("above_50dma")):
            total += 1
            if latest["above_50dma"]:
                above_50 += 1
            if pd.notna(latest.get("above_200dma")) and latest["above_200dma"]:
                above_200 += 1

    if total == 0:
        return Decimal("50.0"), Decimal("50.0")

    return (
        Decimal(str(round(above_50 / total * 100, 1))),
        Decimal(str(round(above_200 / total * 100, 1))),
    )


def _classify_vix(
    vix: Decimal | None,
) -> Literal["low", "normal", "elevated", "extreme"]:
    """Classify VIX level."""
    if vix is None:
        return "normal"
    v = float(vix)
    if v < 14:
        return "low"
    elif v <= 20:
        return "normal"
    elif v <= 28:
        return "elevated"
    return "extreme"


def _count_gaps(
    universe_data: dict[str, pd.DataFrame],
) -> Decimal:
    """Count >1% gaps in last 5 sessions across universe."""
    gap_count = 0

    for df in universe_data.values():
        if len(df) < 6:
            continue
        recent = df.tail(6)
        closes = recent["close"].values
        opens = recent["open"].values
        for i in range(1, len(closes)):
            prev_close = closes[i - 1]
            if prev_close > 0:
                gap_pct = abs(float(opens[i]) - float(prev_close)) / float(prev_close)
                if gap_pct > 0.01:
                    gap_count += 1

    return Decimal(str(gap_count))


def _sector_concentration(
    universe_data: dict[str, pd.DataFrame],
) -> Decimal:
    """Simplified sector concentration: std of per-symbol returns."""
    returns = []
    for df in universe_data.values():
        if len(df) < 2:
            continue
        prev = float(df.iloc[-2]["close"])
        cur = float(df.iloc[-1]["close"])
        ret = (cur - prev) / prev
        returns.append(ret)

    if len(returns) < 2:
        return Decimal("0.50")

    std = float(np.std(returns))
    # Normalize to 0-1 scale (typical daily std is 0.01-0.03)
    score = min(1.0, std / 0.03)
    return Decimal(str(round(score, 2)))


def _correlation_state(
    universe_data: dict[str, pd.DataFrame],
) -> Literal["compressed", "normal", "expanded"]:
    """Simplified correlation: average pairwise correlation of recent returns."""
    all_returns = {}
    for sym, df in universe_data.items():
        if len(df) < 21:
            continue
        series = df.tail(20)["close"].pct_change().dropna()
        if len(series) >= 10:
            all_returns[sym] = series.values

    if len(all_returns) < 2:
        return "normal"

    # Average pairwise correlation
    syms = list(all_returns.keys())
    correlations = []
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            a = all_returns[syms[i]]
            b = all_returns[syms[j]]
            min_len = min(len(a), len(b))
            if min_len >= 5:
                arr_a = np.asarray(a[:min_len])
                arr_b = np.asarray(b[:min_len])
                corr = float(np.corrcoef(arr_a, arr_b)[0, 1])
                if not np.isnan(corr):
                    correlations.append(corr)

    if not correlations:
        return "normal"

    avg_corr = np.mean(correlations)
    if avg_corr > 0.7:
        return "expanded"
    elif avg_corr < 0.3:
        return "compressed"
    return "normal"


def _classify_regime(
    nifty_trend: str,
    breadth_50dma_pct: Decimal,
    vix_state: str,
    gap_freq: Decimal,
) -> RegimeClass:
    """Classify regime based on inputs."""
    stressed_signals = 0
    green_signals = 0

    # NIFTY trend
    if nifty_trend == "bearish":
        stressed_signals += 2
    elif nifty_trend == "bullish":
        green_signals += 2

    # Breadth
    if float(breadth_50dma_pct) < 40:
        stressed_signals += 2
    elif float(breadth_50dma_pct) > 60:
        green_signals += 2

    # VIX
    if vix_state == "extreme":
        stressed_signals += 2
    elif vix_state == "elevated":
        stressed_signals += 1
    elif vix_state == "low":
        green_signals += 1

    # Gaps
    if float(gap_freq) > 5:
        stressed_signals += 1

    # Classification
    if stressed_signals >= 3:
        return RegimeClass.STRESSED
    elif green_signals >= 4:
        return RegimeClass.GREEN
    return RegimeClass.MIXED


def _build_rationale(
    nifty_trend: str,
    breadth_50dma_pct: Decimal,
    vix_state: str,
    gap_freq: Decimal,
) -> str:
    """Build a short rationale string."""
    parts = []
    parts.append(f"NIFTY {nifty_trend}")
    parts.append(f"breadth {breadth_50dma_pct}% above 50-DMA")
    parts.append(f"VIX {vix_state}")
    if float(gap_freq) > 3:
        parts.append(f"elevated gaps ({gap_freq})")
    return ", ".join(parts) + "."
