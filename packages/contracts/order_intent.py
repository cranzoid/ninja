"""OrderIntent schema — rule-engine-validated order intent."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from .enums import (
    ExecutionTiming,
    Mode,
    OrderSide,
    OrderType,
    PortfolioLayer,
    RegimeClass,
)


class OrderIntent(BaseModel):
    """
    A validated, risk-checked intent to place an order.

    Output of the rule engine. This is NOT a broker order yet — it must
    pass the execution gate before reaching the paper or live broker.
    The rule engine is the deterministic authority layer; no model output
    alone can produce a valid OrderIntent (charter §4).
    """

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "intent_id": "550e8400-e29b-41d4-a716-446655440000",
                    "symbol": "RELIANCE",
                    "layer": "swing",
                    "side": "buy",
                    "order_type": "market",
                    "quantity": 5,
                    "limit_price": None,
                    "stop_price": "2780.00",
                    "risk_amount": "350.00",
                    "risk_pct_of_equity": "0.35",
                    "execution_timing": "next_open",
                    "source_trade_card_id": "trade-card-abc123",
                    "regime_at_intent": "green",
                    "created_at": "2026-03-26T15:30:00Z",
                    "approved_by": "rule_engine",
                    "mode": "paper",
                },
                {
                    "intent_id": "550e8400-e29b-41d4-a716-446655440001",
                    "symbol": "TCS",
                    "layer": "core",
                    "side": "buy",
                    "order_type": "limit",
                    "quantity": 2,
                    "limit_price": "3820.00",
                    "stop_price": "3750.00",
                    "risk_amount": "140.00",
                    "risk_pct_of_equity": "0.14",
                    "execution_timing": "next_open",
                    "source_trade_card_id": None,
                    "regime_at_intent": "mixed",
                    "created_at": "2026-03-26T15:30:00Z",
                    "approved_by": "operator_override",
                    "mode": "paper",
                },
            ]
        },
    )

    intent_id: str
    """UUID identifying this intent."""

    symbol: str
    layer: PortfolioLayer
    side: OrderSide
    order_type: OrderType

    quantity: int
    """Number of shares. Must be > 0."""

    limit_price: Decimal | None = None
    """Required when order_type is LIMIT."""

    stop_price: Decimal
    """Protective stop for this position."""

    risk_amount: Decimal
    """Position risk in rupees (quantity x risk_per_share)."""

    risk_pct_of_equity: Decimal
    """Risk as percentage of total equity. Charter limits apply (§6.3)."""

    execution_timing: ExecutionTiming
    regime_at_intent: RegimeClass
    created_at: datetime

    source_trade_card_id: str | None = None
    """Reference to the TradeCard if this intent was AI-assisted."""

    approved_by: Literal["rule_engine", "operator_override"]
    mode: Mode

    @model_validator(mode="after")
    def validate_intent(self) -> "OrderIntent":
        if self.quantity <= 0:
            raise ValueError("quantity must be > 0")

        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price is required when order_type is LIMIT")

        if self.layer == PortfolioLayer.SWING and self.risk_pct_of_equity > Decimal(
            "0.50"
        ):
            raise ValueError(
                f"SWING risk_pct_of_equity ({self.risk_pct_of_equity}%) "
                f"exceeds charter limit of 0.50% (§6.3)"
            )

        if self.layer == PortfolioLayer.CORE and self.risk_pct_of_equity > Decimal(
            "0.25"
        ):
            raise ValueError(
                f"CORE risk_pct_of_equity ({self.risk_pct_of_equity}%) "
                f"exceeds charter limit of 0.25% (§6.3)"
            )

        return self
