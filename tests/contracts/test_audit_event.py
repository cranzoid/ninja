"""Tests for AuditEvent schema."""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from packages.contracts import AuditEvent
from packages.contracts.enums import Mode

_TS = datetime(2026, 3, 26, 9, 15, 0, tzinfo=UTC)


def _event(**overrides: Any) -> AuditEvent:
    defaults: dict[str, Any] = {
        "event_id": "550e8400-e29b-41d4-a716-446655440010",
        "timestamp": _TS,
        "event_type": "trade_card_generated",
        "source_service": "model-router",
        "mode": Mode.PAPER,
        "payload": {"symbol": "RELIANCE", "model_provider": "anthropic"},
    }
    defaults.update(overrides)
    return AuditEvent(**defaults)


# --- Normal cases ---

def test_trade_card_generated_event() -> None:
    event = _event()
    assert event.event_type == "trade_card_generated"
    assert event.operator_visible is True
    assert event.related_symbol is None


def test_schema_validation_failure_event() -> None:
    event = _event(
        event_id="550e8400-e29b-41d4-a716-446655440011",
        event_type="schema_validation_failure",
        payload={
            "model_id": "claude-haiku-4-5",
            "errors": ["stop_price must be below entry_price_target"],
            "retry_count": 1,
        },
        related_symbol="INFY",
    )
    assert event.event_type == "schema_validation_failure"
    assert event.related_symbol == "INFY"
    assert event.payload["retry_count"] == 1


def test_regime_change_event_with_optional_fields() -> None:
    event = _event(
        event_type="regime_change",
        payload={"from": "green", "to": "mixed", "breadth_pct": 48.5},
        related_symbol=None,
        related_intent_id=None,
        operator_visible=True,
    )
    assert event.event_type == "regime_change"
    assert event.related_intent_id is None


# --- Failure cases ---

def test_non_json_serializable_payload_rejected() -> None:
    with pytest.raises(ValidationError, match="payload must be JSON-serializable"):
        _event(payload={"bad_value": {1, 2, 3}})  # sets are not JSON-serializable


def test_missing_required_event_type_rejected() -> None:
    with pytest.raises(ValidationError):
        AuditEvent(  # type: ignore[call-arg]
            event_id="abc",
            timestamp=_TS,
            # event_type is missing
            source_service="test",
            mode=Mode.PAPER,
            payload={},
        )


def test_invalid_mode_rejected() -> None:
    with pytest.raises(ValidationError):
        _event(mode="invalid-mode")


# --- Round-trip ---

def test_serialization_round_trip() -> None:
    event = _event(
        related_symbol="RELIANCE",
        related_intent_id="intent-abc-123",
    )
    json_str = event.model_dump_json()
    restored = AuditEvent.model_validate_json(json_str)
    assert restored == event


# --- Schema export ---

def test_schema_export() -> None:
    schema = AuditEvent.model_json_schema()
    assert isinstance(schema, dict)
    assert schema["title"] == "AuditEvent"
    assert "properties" in schema
    assert "examples" in schema
