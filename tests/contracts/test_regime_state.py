"""Tests for RegimeState schema."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from packages.contracts import RegimeState
from packages.contracts.enums import RegimeClass

_TS = datetime(2026, 3, 26, 9, 0, 0, tzinfo=UTC)


def _state(**overrides: Any) -> RegimeState:
    defaults: dict[str, Any] = {
        "assessed_at": _TS,
        "regime_class": RegimeClass.GREEN,
        "nifty50_trend": "bullish",
        "breadth_above_50dma_pct": Decimal("72.5"),
        "breadth_above_200dma_pct": Decimal("81.0"),
        "vix_level": Decimal("14.2"),
        "vix_state": "low",
        "gap_frequency_5d": Decimal("0.8"),
        "sector_concentration_score": Decimal("0.35"),
        "correlation_state": "normal",
        "sizing_multiplier": Decimal("1.0"),
        "rationale": "Broad participation above key MAs, VIX subdued.",
    }
    defaults.update(overrides)
    return RegimeState(**defaults)


# --- Normal cases ---

def test_green_regime_full_sizing() -> None:
    state = _state()
    assert state.regime_class == RegimeClass.GREEN
    assert state.sizing_multiplier == Decimal("1.0")
    assert state.vix_level == Decimal("14.2")


def test_mixed_regime_half_sizing() -> None:
    state = _state(
        regime_class=RegimeClass.MIXED,
        nifty50_trend="neutral",
        breadth_above_50dma_pct=Decimal("52.0"),
        breadth_above_200dma_pct=Decimal("63.0"),
        vix_state="normal",
        gap_frequency_5d=Decimal("1.5"),
        sector_concentration_score=Decimal("0.55"),
        sizing_multiplier=Decimal("0.5"),
        rationale="Mixed signals: moderate breadth but rising gap frequency.",
    )
    assert state.regime_class == RegimeClass.MIXED
    assert state.sizing_multiplier == Decimal("0.5")


def test_stressed_regime_no_new_swings() -> None:
    state = _state(
        regime_class=RegimeClass.STRESSED,
        nifty50_trend="bearish",
        breadth_above_50dma_pct=Decimal("28.0"),
        breadth_above_200dma_pct=Decimal("45.0"),
        vix_level=Decimal("28.5"),
        vix_state="elevated",
        gap_frequency_5d=Decimal("3.2"),
        sector_concentration_score=Decimal("0.72"),
        correlation_state="expanded",
        sizing_multiplier=Decimal("0.0"),
        rationale="Weak breadth, elevated VIX, high gap frequency: stressed.",
    )
    assert state.regime_class == RegimeClass.STRESSED
    assert state.sizing_multiplier == Decimal("0.0")


# --- Failure cases ---

def test_wrong_multiplier_for_green_rejected() -> None:
    with pytest.raises(ValidationError, match=r"must be 1\.0 for green"):
        _state(
            regime_class=RegimeClass.GREEN,
            sizing_multiplier=Decimal("0.5"),
        )


def test_wrong_multiplier_for_mixed_rejected() -> None:
    with pytest.raises(ValidationError, match=r"must be 0\.5 for mixed"):
        _state(
            regime_class=RegimeClass.MIXED,
            sizing_multiplier=Decimal("1.0"),
            nifty50_trend="neutral",
            breadth_above_50dma_pct=Decimal("50.0"),
            breadth_above_200dma_pct=Decimal("60.0"),
            vix_state="normal",
            gap_frequency_5d=Decimal("1.2"),
            sector_concentration_score=Decimal("0.50"),
        )


def test_invalid_nifty50_trend_rejected() -> None:
    with pytest.raises(ValidationError):
        _state(nifty50_trend="sideways")


# --- Round-trip ---

def test_serialization_round_trip() -> None:
    state = _state()
    json_str = state.model_dump_json()
    restored = RegimeState.model_validate_json(json_str)
    assert restored == state


# --- Schema export ---

def test_schema_export() -> None:
    schema = RegimeState.model_json_schema()
    assert isinstance(schema, dict)
    assert schema["title"] == "RegimeState"
    assert "properties" in schema
    assert "examples" in schema
