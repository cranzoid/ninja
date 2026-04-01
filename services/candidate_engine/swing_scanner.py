"""Swing candidate scanner — implements charter §6.5 entry conditions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd

from packages.contracts.candidates import SwingCandidate
from packages.contracts.enums import RegimeClass
from packages.contracts.regime_state import RegimeState


def scan_swing_candidates(
    featured_data: dict[str, pd.DataFrame],
    regime: RegimeState,
) -> list[SwingCandidate]:
    """
    Scan featured OHLCV data for swing entry candidates.

    Checks charter §6.5 conditions on the latest row of each symbol's data.
    Returns all scanned symbols (passing and failing) for operator visibility.
    """
    candidates: list[SwingCandidate] = []

    for symbol, df in featured_data.items():
        if df.empty or pd.isna(df.iloc[-1].get("dma_50")):
            continue

        row = df.iloc[-1]
        raw_date = row["date"]
        scan_date_val: date = (
            raw_date if isinstance(raw_date, date) else raw_date.date()
        )
        close = Decimal(str(round(float(row["close"]), 2)))
        atr_val = (
            Decimal(str(round(float(row["atr_14"]), 2)))
            if pd.notna(row.get("atr_14"))
            else Decimal("0")
        )
        vol_ratio = (
            Decimal(str(round(float(row["volume_ratio_20d"]), 4)))
            if pd.notna(row.get("volume_ratio_20d"))
            else Decimal("0")
        )

        # Entry price estimate = latest close (proxy for next open)
        entry_price = close
        # Stop = 2x ATR below entry
        stop_price = entry_price - 2 * atr_val
        risk_per_share = entry_price - stop_price

        # Check entry conditions
        failed: list[str] = []

        if not bool(row.get("above_50dma", False)):
            failed.append("close_below_50dma")

        if not bool(row.get("dma_50_above_200", False)):
            failed.append("50dma_below_200dma")

        if not bool(row.get("close_above_20d_high", False)):
            failed.append("close_below_20d_high")

        if not bool(row.get("volume_sufficient", False)):
            failed.append("volume_insufficient")

        if regime.regime_class == RegimeClass.STRESSED:
            failed.append("regime_stressed")

        candidates.append(SwingCandidate(
            symbol=symbol,
            scan_date=scan_date_val,
            close=close,
            entry_price_estimate=entry_price,
            stop_price=stop_price,
            risk_per_share=risk_per_share,
            volume_ratio=vol_ratio,
            atr_14=atr_val,
            regime_at_scan=regime.regime_class,
            passes_all_entry_conditions=len(failed) == 0,
            failed_conditions=failed,
        ))

    return candidates
