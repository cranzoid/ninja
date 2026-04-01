"""Tests for validate_contract and validate_json_string utilities."""

import json
from datetime import UTC, datetime

from packages.contracts import AuditEvent, validate_contract, validate_json_string
from packages.contracts.enums import Mode

_TS = datetime(2026, 3, 26, 9, 15, 0, tzinfo=UTC)


def _valid_event_dict() -> dict[str, object]:
    return {
        "event_id": "550e8400-e29b-41d4-a716-446655440099",
        "timestamp": _TS,
        "event_type": "test_event",
        "source_service": "test-service",
        "mode": Mode.PAPER,
        "payload": {"key": "value", "count": 1},
    }


def _valid_event_json() -> str:
    return json.dumps({
        "event_id": "550e8400-e29b-41d4-a716-446655440099",
        "timestamp": "2026-03-26T09:15:00Z",
        "event_type": "test_event",
        "source_service": "test-service",
        "mode": "paper",
        "payload": {"key": "value", "count": 1},
    })


# --- validate_contract ---

def test_validate_contract_success() -> None:
    model, errors = validate_contract(_valid_event_dict(), AuditEvent)
    assert model is not None
    assert errors == []
    assert model.event_type == "test_event"


def test_validate_contract_missing_field() -> None:
    data = _valid_event_dict()
    del data["event_type"]
    model, errors = validate_contract(data, AuditEvent)
    assert model is None
    assert len(errors) > 0
    assert any("event_type" in e for e in errors)


def test_validate_contract_business_rule_violation() -> None:
    """Non-JSON-serializable payload triggers business rule validator."""
    data = _valid_event_dict()
    data["payload"] = {"bad": {1, 2, 3}}
    model, errors = validate_contract(data, AuditEvent)
    assert model is None
    assert len(errors) > 0
    assert any("JSON-serializable" in e for e in errors)


# --- validate_json_string ---

def test_validate_json_string_success() -> None:
    model, errors = validate_json_string(_valid_event_json(), AuditEvent)
    assert model is not None
    assert errors == []
    assert model.mode == Mode.PAPER


def test_validate_json_string_missing_required_field() -> None:
    bad_json = json.dumps({
        "event_id": "abc",
        "timestamp": "2026-03-26T09:15:00Z",
        # event_type missing
        "source_service": "test",
        "mode": "paper",
        "payload": {},
    })
    model, errors = validate_json_string(bad_json, AuditEvent)
    assert model is None
    assert len(errors) > 0


def test_validate_json_string_malformed_json() -> None:
    model, errors = validate_json_string("{not valid json", AuditEvent)
    assert model is None
    assert len(errors) > 0


# --- Never raises ---

def test_validate_contract_never_raises() -> None:
    """validate_contract must not raise even for completely wrong input."""
    model, errors = validate_contract({"garbage": True}, AuditEvent)
    assert model is None
    assert len(errors) > 0


def test_validate_json_string_never_raises() -> None:
    """validate_json_string must not raise even for empty string."""
    model, errors = validate_json_string("", AuditEvent)
    assert model is None
    assert len(errors) > 0
