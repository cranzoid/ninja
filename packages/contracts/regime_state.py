"""RegimeState schema — output of the regime engine."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from .enums import RegimeClass


class RegimeState(BaseModel):
    """
    Market regime assessment from the regime engine (charter §6.7).

    Drives sizing multipliers across the platform:
    - GREEN:   normal sizing (multiplier 1.0)
    - MIXED:   half-sized swing entries (multiplier 0.5)
    - STRESSED: no new swings, core adds only (multiplier 0.0)
    """

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "assessed_at": "2026-03-26T09:00:00Z",
                    "regime_class": "green",
                    "nifty50_trend": "bullish",
                    "breadth_above_50dma_pct": "72.5",
                    "breadth_above_200dma_pct": "81.0",
                    "vix_level": "14.2",
                    "vix_state": "low",
                    "gap_frequency_5d": "0.8",
                    "sector_concentration_score": "0.35",
                    "correlation_state": "normal",
                    "sizing_multiplier": "1.0",
                    "rationale": "Broad MAs, VIX subdued, low gap frequency.",
                },
                {
                    "assessed_at": "2026-03-26T09:00:00Z",
                    "regime_class": "stressed",
                    "nifty50_trend": "bearish",
                    "breadth_above_50dma_pct": "28.0",
                    "breadth_above_200dma_pct": "45.0",
                    "vix_level": "28.5",
                    "vix_state": "elevated",
                    "gap_frequency_5d": "3.2",
                    "sector_concentration_score": "0.72",
                    "correlation_state": "expanded",
                    "sizing_multiplier": "0.0",
                    "rationale": "Weak breadth, elevated VIX, high gaps.",
                },
            ]
        },
    )

    assessed_at: datetime
    """UTC timestamp of this regime assessment."""

    regime_class: RegimeClass

    nifty50_trend: Literal["bullish", "bearish", "neutral"]
    """NIFTY 50 trend state."""

    breadth_above_50dma_pct: Decimal
    """Percentage of tracked names trading above 50-DMA (0-100)."""

    breadth_above_200dma_pct: Decimal
    """Percentage of tracked names trading above 200-DMA (0-100)."""

    vix_level: Decimal | None = None
    """India VIX level if available."""

    vix_state: Literal["low", "normal", "elevated", "extreme"]

    gap_frequency_5d: Decimal
    """Number of >1% gaps in last 5 sessions across the universe."""

    sector_concentration_score: Decimal
    """0-1 score; higher = more concentrated sector leadership."""

    correlation_state: Literal["compressed", "normal", "expanded"]

    sizing_multiplier: Decimal
    """
    Sizing multiplier for new entries.
    GREEN=1.0, MIXED=0.5, STRESSED=0.0 (for swings).
    """

    rationale: str
    """1-2 sentence explanation of the regime classification."""

    @model_validator(mode="after")
    def validate_sizing_multiplier(self) -> "RegimeState":
        expected = {
            RegimeClass.GREEN: Decimal("1.0"),
            RegimeClass.MIXED: Decimal("0.5"),
            RegimeClass.STRESSED: Decimal("0.0"),
        }
        if self.sizing_multiplier != expected[self.regime_class]:
            raise ValueError(
                f"sizing_multiplier must be {expected[self.regime_class]} "
                f"for {self.regime_class} regime"
            )
        return self
