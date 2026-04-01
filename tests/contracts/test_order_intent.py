"""Tests for OrderIntent schema."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from packages.contracts import OrderIntent
from packages.contracts.enums import (
    ExecutionTiming,
    Mode,
    OrderSide,
    OrderType,
    PortfolioLayer,
    RegimeClass,
)

_TS = datetime(2026, 3, 26, 15, 30, 0, tzinfo=UTC)


def _intent(**overrides: Any) -> OrderIntent:
    defaults: dict[str, Any] = {
        "intent_id": "550e8400-e29b-41d4-a716-446655440000",
        "symbol": "RELIANCE",
        "layer": PortfolioLayer.SWING,
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "quantity": 5,
        "stop_price": Decimal("2780.00"),
        "risk_amount": Decimal("350.00"),
        "risk_pct_of_equity": Decimal("0.35"),
        "execution_timing": ExecutionTiming.NEXT_OPEN,
        "regime_at_intent": RegimeClass.GREEN,
        "created_at": _TS,
        "approved_by": "rule_engine",
        "mode": Mode.PAPER,
    }
    defaults.update(overrides)
    return OrderIntent(**defaults)


# --- Normal cases ---

def test_valid_swing_market_order() -> None:
    intent = _intent()
    assert intent.symbol == "RELIANCE"
    assert intent.layer == PortfolioLayer.SWING
    assert intent.order_type == OrderType.MARKET
    assert intent.limit_price is None
    assert intent.source_trade_card_id is None


def test_valid_core_limit_order() -> None:
    intent = _intent(
        symbol="TCS",
        layer=PortfolioLayer.CORE,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("3820.00"),
        stop_price=Decimal("3750.00"),
        risk_amount=Decimal("140.00"),
        risk_pct_of_equity=Decimal("0.14"),
        regime_at_intent=RegimeClass.MIXED,
        approved_by="operator_override",
        source_trade_card_id="trade-card-abc123",
    )
    assert intent.symbol == "TCS"
    assert intent.limit_price == Decimal("3820.00")
    assert intent.approved_by == "operator_override"


def test_valid_swing_at_max_risk() -> None:
    """Swing at exactly 0.50% risk is accepted."""
    intent = _intent(risk_pct_of_equity=Decimal("0.50"))
    assert intent.risk_pct_of_equity == Decimal("0.50")


# --- Failure cases ---

def test_swing_risk_over_limit_rejected() -> None:
    with pytest.raises(ValidationError, match="SWING risk_pct_of_equity"):
        _intent(
            layer=PortfolioLayer.SWING,
            risk_pct_of_equity=Decimal("0.51"),
        )


def test_core_risk_over_limit_rejected() -> None:
    with pytest.raises(ValidationError, match="CORE risk_pct_of_equity"):
        _intent(
            layer=PortfolioLayer.CORE,
            risk_pct_of_equity=Decimal("0.26"),
        )


def test_limit_order_without_price_rejected() -> None:
    with pytest.raises(ValidationError, match="limit_price is required"):
        _intent(
            order_type=OrderType.LIMIT,
            limit_price=None,
        )


# --- Round-trip ---

def test_serialization_round_trip() -> None:
    intent = _intent(
        order_type=OrderType.LIMIT,
        limit_price=Decimal("2850.00"),
    )
    json_str = intent.model_dump_json()
    restored = OrderIntent.model_validate_json(json_str)
    assert restored == intent


# --- Schema export ---

def test_schema_export() -> None:
    schema = OrderIntent.model_json_schema()
    assert isinstance(schema, dict)
    assert schema["title"] == "OrderIntent"
    assert "properties" in schema
    assert "examples" in schema
