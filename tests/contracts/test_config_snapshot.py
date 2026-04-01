"""Tests for ConfigSnapshot and RiskLimits schemas."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from packages.contracts import ConfigSnapshot, RiskLimits
from packages.contracts.enums import Mode, RegimeClass

_TS = datetime(2026, 3, 26, 9, 0, 0, tzinfo=UTC)
_CHECKSUM = "a3b4c5d6e7f8a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a1b2c3d4e5f6a7b8"


def _snapshot(**overrides: Any) -> ConfigSnapshot:
    defaults: dict[str, Any] = {
        "snapshot_id": "550e8400-e29b-41d4-a716-446655440020",
        "captured_at": _TS,
        "mode": Mode.PAPER,
        "armed_live": False,
        "risk_limits": RiskLimits(),
        "regime_state": RegimeClass.GREEN,
        "universe_size": 98,
        "active_blockers_count": 3,
        "config_checksum": _CHECKSUM,
    }
    defaults.update(overrides)
    return ConfigSnapshot(**defaults)


# --- Normal cases ---

def test_paper_snapshot_with_defaults() -> None:
    snapshot = _snapshot()
    assert snapshot.mode == Mode.PAPER
    assert snapshot.armed_live is False
    assert snapshot.risk_limits.swing_risk_per_trade_pct == Decimal("0.50")
    assert snapshot.risk_limits.max_new_swing_entries_per_day == 2


def test_snapshot_with_custom_risk_limits() -> None:
    tighter = RiskLimits(
        swing_risk_per_trade_pct=Decimal("0.35"),
        core_add_risk_pct=Decimal("0.20"),
        core_position_cap_pct=Decimal("10.0"),
        swing_position_cap_pct=Decimal("6.0"),
        sector_cap_pct=Decimal("20.0"),
        aggregate_open_risk_pct=Decimal("3.0"),
        max_new_swing_entries_per_day=1,
    )
    snapshot = _snapshot(risk_limits=tighter, universe_size=75)
    assert snapshot.risk_limits.swing_risk_per_trade_pct == Decimal("0.35")
    assert snapshot.universe_size == 75


def test_stressed_regime_snapshot() -> None:
    snapshot = _snapshot(
        regime_state=RegimeClass.STRESSED,
        active_blockers_count=12,
    )
    assert snapshot.regime_state == RegimeClass.STRESSED
    assert snapshot.active_blockers_count == 12


# --- Failure cases ---

def test_missing_checksum_rejected() -> None:
    with pytest.raises(ValidationError):
        ConfigSnapshot(  # type: ignore[call-arg]
            snapshot_id="abc",
            captured_at=_TS,
            mode=Mode.PAPER,
            armed_live=False,
            risk_limits=RiskLimits(),
            regime_state=RegimeClass.GREEN,
            universe_size=50,
            active_blockers_count=0,
            # config_checksum missing
        )


def test_invalid_mode_rejected() -> None:
    with pytest.raises(ValidationError):
        _snapshot(mode="invalid")


def test_float_for_int_field_rejected_in_strict_mode() -> None:
    """strict=True rejects float where int is required."""
    with pytest.raises(ValidationError):
        _snapshot(universe_size=98.5)


# --- Round-trip ---

def test_serialization_round_trip() -> None:
    snapshot = _snapshot()
    json_str = snapshot.model_dump_json()
    restored = ConfigSnapshot.model_validate_json(json_str)
    assert restored == snapshot


# --- Schema export ---

def test_schema_export() -> None:
    schema = ConfigSnapshot.model_json_schema()
    assert isinstance(schema, dict)
    assert schema["title"] == "ConfigSnapshot"
    assert "properties" in schema
