"""TradeCard schema — structured output from the thesis extractor AI role."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from .enums import PortfolioLayer, RegimeClass, SignalDirection


class TradeCard(BaseModel):
    """
    Structured trade thesis for a shortlisted name.

    Output of the thesis extractor AI role (charter §7.2).
    Consumed by the blocker classifier and rule engine.
    """

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "symbol": "RELIANCE",
                    "layer": "swing",
                    "direction": "long",
                    "thesis_summary": "Reliance 20-day breakout on elevated volume.",
                    "entry_price_target": "2850.00",
                    "stop_price": "2780.00",
                    "risk_per_share": "70.00",
                    "reward_target_1": "2990.00",
                    "atr_14": "45.00",
                    "dma_200": "2650.00",
                    "dma_50": "2720.00",
                    "volume_ratio_20d": "1.45",
                    "regime_at_generation": "green",
                    "generated_at": "2026-03-26T09:15:00Z",
                    "model_provider": "anthropic",
                    "model_id": "claude-sonnet-4-6",
                    "confidence_tag": "high",
                },
                {
                    "symbol": "TCS",
                    "layer": "core",
                    "direction": "long",
                    "thesis_summary": "TCS above 200-DMA, steady revenue, core add.",
                    "entry_price_target": "3820.00",
                    "stop_price": "3750.00",
                    "risk_per_share": "70.00",
                    "reward_target_1": None,
                    "atr_14": "62.00",
                    "dma_200": "3700.00",
                    "dma_50": "3780.00",
                    "volume_ratio_20d": "0.95",
                    "regime_at_generation": "mixed",
                    "generated_at": "2026-03-26T09:15:00Z",
                    "model_provider": "anthropic",
                    "model_id": "claude-sonnet-4-6",
                    "confidence_tag": None,
                },
            ]
        },
    )

    symbol: str
    """NSE trading symbol, e.g. 'RELIANCE'."""

    layer: PortfolioLayer
    direction: SignalDirection

    thesis_summary: str
    """1-3 sentence rationale from the AI. The only prose field."""

    entry_price_target: Decimal
    """Expected entry level (next-day open)."""

    stop_price: Decimal
    """Protective stop — must be below entry for LONG direction."""

    risk_per_share: Decimal
    """Computed as entry_price_target - stop_price."""

    reward_target_1: Decimal | None = None
    """First partial exit target. For swing: +2R. Optional for core."""

    atr_14: Decimal
    """14-period Average True Range at time of analysis."""

    dma_200: Decimal
    """200-day moving average."""

    dma_50: Decimal
    """50-day moving average."""

    volume_ratio_20d: Decimal
    """Current volume / 20-day average volume."""

    regime_at_generation: RegimeClass
    """Market regime when this card was generated."""

    generated_at: datetime
    """UTC timestamp of generation."""

    model_provider: str
    """AI provider that generated this card, e.g. 'anthropic'."""

    model_id: str
    """Specific model version, e.g. 'claude-sonnet-4-6'."""

    confidence_tag: str | None = None
    """Optional self-assessed confidence label from the model."""

    @model_validator(mode="after")
    def validate_prices_and_risk(self) -> "TradeCard":
        if (
            self.direction == SignalDirection.LONG
            and self.stop_price >= self.entry_price_target
        ):
            raise ValueError(
                "stop_price must be strictly below entry_price_target for LONG"
            )
        computed_risk = self.entry_price_target - self.stop_price
        if self.risk_per_share != computed_risk:
            raise ValueError(
                f"risk_per_share ({self.risk_per_share}) must equal "
                f"entry_price_target - stop_price ({computed_risk})"
            )
        return self
