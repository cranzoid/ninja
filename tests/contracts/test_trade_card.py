"""Tests for TradeCard schema."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from packages.contracts import TradeCard
from packages.contracts.enums import PortfolioLayer, RegimeClass, SignalDirection

_TS = datetime(2026, 3, 26, 9, 15, 0, tzinfo=UTC)


def _card(**overrides: Any) -> TradeCard:
    """Build a valid RELIANCE swing TradeCard with sensible defaults."""
    defaults: dict[str, Any] = {
        "symbol": "RELIANCE",
        "layer": PortfolioLayer.SWING,
        "direction": SignalDirection.LONG,
        "thesis_summary": "Reliance breaks 20-day high on elevated volume above MAs.",
        "entry_price_target": Decimal("2850.00"),
        "stop_price": Decimal("2780.00"),
        "risk_per_share": Decimal("70.00"),
        "reward_target_1": Decimal("2990.00"),
        "atr_14": Decimal("45.00"),
        "dma_200": Decimal("2650.00"),
        "dma_50": Decimal("2720.00"),
        "volume_ratio_20d": Decimal("1.45"),
        "regime_at_generation": RegimeClass.GREEN,
        "generated_at": _TS,
        "model_provider": "anthropic",
        "model_id": "claude-sonnet-4-6",
    }
    defaults.update(overrides)
    return TradeCard(**defaults)


# --- Normal cases ---

def test_valid_swing_trade_card() -> None:
    card = _card()
    assert card.symbol == "RELIANCE"
    assert card.layer == PortfolioLayer.SWING
    assert card.risk_per_share == Decimal("70.00")
    assert card.confidence_tag is None


def test_valid_core_trade_card() -> None:
    card = _card(
        symbol="TCS",
        layer=PortfolioLayer.CORE,
        entry_price_target=Decimal("3820.00"),
        stop_price=Decimal("3750.00"),
        risk_per_share=Decimal("70.00"),
        reward_target_1=None,
        atr_14=Decimal("62.00"),
        dma_200=Decimal("3700.00"),
        dma_50=Decimal("3780.00"),
        volume_ratio_20d=Decimal("0.95"),
        regime_at_generation=RegimeClass.MIXED,
    )
    assert card.symbol == "TCS"
    assert card.layer == PortfolioLayer.CORE
    assert card.reward_target_1 is None


def test_valid_card_with_confidence_tag() -> None:
    card = _card(
        symbol="INFY",
        entry_price_target=Decimal("1580.00"),
        stop_price=Decimal("1540.00"),
        risk_per_share=Decimal("40.00"),
        atr_14=Decimal("28.00"),
        dma_200=Decimal("1480.00"),
        dma_50=Decimal("1520.00"),
        volume_ratio_20d=Decimal("1.62"),
        reward_target_1=Decimal("1660.00"),
        confidence_tag="high",
    )
    assert card.symbol == "INFY"
    assert card.confidence_tag == "high"


# --- Failure cases ---

def test_stop_above_entry_rejected() -> None:
    with pytest.raises(ValidationError, match="stop_price must be strictly below"):
        _card(
            entry_price_target=Decimal("2850.00"),
            stop_price=Decimal("2900.00"),
            risk_per_share=Decimal("-50.00"),
        )


def test_stop_equal_entry_rejected() -> None:
    with pytest.raises(ValidationError):
        _card(
            entry_price_target=Decimal("2850.00"),
            stop_price=Decimal("2850.00"),
            risk_per_share=Decimal("0.00"),
        )


def test_risk_per_share_mismatch_rejected() -> None:
    with pytest.raises(ValidationError, match="risk_per_share"):
        _card(
            entry_price_target=Decimal("2850.00"),
            stop_price=Decimal("2780.00"),
            risk_per_share=Decimal("100.00"),  # should be 70.00
        )


# --- Round-trip ---

def test_serialization_round_trip() -> None:
    card = _card()
    json_str = card.model_dump_json()
    restored = TradeCard.model_validate_json(json_str)
    assert restored == card


# --- Schema export ---

def test_schema_export() -> None:
    schema = TradeCard.model_json_schema()
    assert isinstance(schema, dict)
    assert schema["title"] == "TradeCard"
    assert "properties" in schema
    assert "examples" in schema
