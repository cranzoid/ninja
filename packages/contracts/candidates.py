"""Candidate schemas — output of the candidate engine scanners."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from .enums import RegimeClass


class SwingCandidate(BaseModel):
    """Output of the swing candidate scanner (charter §6.5 entry conditions)."""

    model_config = ConfigDict(strict=True, frozen=True)

    symbol: str
    scan_date: date
    close: Decimal
    entry_price_estimate: Decimal
    stop_price: Decimal
    risk_per_share: Decimal
    volume_ratio: Decimal
    atr_14: Decimal
    regime_at_scan: RegimeClass
    passes_all_entry_conditions: bool
    failed_conditions: list[str]


class CoreCandidate(BaseModel):
    """Output of the core candidate scanner (charter §6.4 entry conditions)."""

    model_config = ConfigDict(strict=True, frozen=True)

    symbol: str
    scan_date: date
    close: Decimal
    dma_200: Decimal
    dma_50: Decimal
    extension_from_50dma_pct: Decimal
    above_200dma: bool
    is_extended: bool
    regime_at_scan: RegimeClass
    passes_entry_conditions: bool
    failed_conditions: list[str]
