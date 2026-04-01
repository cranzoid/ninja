"""Core candidate scanner — implements charter §6.4 entry conditions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd

from packages.contracts.candidates import CoreCandidate
from packages.contracts.enums import RegimeClass
from packages.contracts.regime_state import RegimeState


def scan_core_candidates(
    featured_data: dict[str, pd.DataFrame],
    regime: RegimeState,
) -> list[CoreCandidate]:
    """
    Scan featured OHLCV data for core entry candidates.

    Checks charter §6.4 conditions on the latest row of each symbol's data.
    Returns all scanned symbols (passing and failing) for operator visibility.
    """
    candidates: list[CoreCandidate] = []

    for symbol, df in featured_data.items():
        if df.empty or pd.isna(df.iloc[-1].get("dma_200")):
            continue

        row = df.iloc[-1]
        raw_date = row["date"]
        scan_date_val: date = (
            raw_date if isinstance(raw_date, date) else raw_date.date()
        )
        close = Decimal(str(round(float(row["close"]), 2)))
        dma_200_val = Decimal(str(round(float(row["dma_200"]), 2)))
        dma_50_val = Decimal(str(round(float(row["dma_50"]), 2)))

        above_200 = bool(row.get("above_200dma", False))
        is_ext = bool(row.get("extended_above_50dma", False))
        ext_pct = Decimal(str(round(
            (float(row["close"]) - float(row["dma_50"])) / float(row["dma_50"]) * 100, 2
        ))) if float(row["dma_50"]) > 0 else Decimal("0")

        failed: list[str] = []

        if not above_200:
            failed.append("below_200dma")

        if is_ext:
            failed.append("extended_above_50dma")

        if regime.regime_class == RegimeClass.STRESSED:
            failed.append("regime_stressed")

        candidates.append(CoreCandidate(
            symbol=symbol,
            scan_date=scan_date_val,
            close=close,
            dma_200=dma_200_val,
            dma_50=dma_50_val,
            extension_from_50dma_pct=ext_pct,
            above_200dma=above_200,
            is_extended=is_ext,
            regime_at_scan=regime.regime_class,
            passes_entry_conditions=len(failed) == 0,
            failed_conditions=failed,
        ))

    return candidates
