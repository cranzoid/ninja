"""Tests for BlockerReport and BlockerDetail schemas."""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from packages.contracts import BlockerDetail, BlockerReport
from packages.contracts.enums import BlockerCategory

_TS = datetime(2026, 3, 26, 9, 15, 0, tzinfo=UTC)
_EXPIRY = datetime(2026, 3, 31, 0, 0, 0, tzinfo=UTC)


def _detail(**overrides: Any) -> BlockerDetail:
    defaults: dict[str, Any] = {
        "category": BlockerCategory.EARNINGS_WINDOW,
        "severity": "hard",
        "reason": "Q4 results scheduled in 5 days. Entry blocked per rule S1.",
        "source_category": "earnings_calendar",
    }
    defaults.update(overrides)
    return BlockerDetail(**defaults)


def _report(**overrides: Any) -> BlockerReport:
    defaults: dict[str, Any] = {
        "symbol": "HDFCBANK",
        "scan_timestamp": _TS,
        "blockers_found": [],
        "is_blocked": False,
        "model_provider": "anthropic",
        "model_id": "claude-haiku-4-5",
    }
    defaults.update(overrides)
    return BlockerReport(**defaults)


# --- Normal cases ---

def test_clean_scan_no_blockers() -> None:
    report = _report(symbol="INFY")
    assert report.symbol == "INFY"
    assert report.blockers_found == []
    assert report.is_blocked is False


def test_soft_blocker_not_blocked() -> None:
    """A soft blocker does not set is_blocked=True."""
    soft = _detail(
        category=BlockerCategory.SECTOR_SHOCK,
        severity="soft",
        reason="Sector saw sharp sell-off yesterday; monitor before entry.",
        source_category="market_data",
    )
    report = _report(
        symbol="ICICIBANK",
        blockers_found=[soft],
        is_blocked=False,
    )
    assert report.is_blocked is False
    assert len(report.blockers_found) == 1


def test_hard_blocker_sets_is_blocked() -> None:
    hard = _detail(expires_at=_EXPIRY)
    report = _report(
        symbol="HDFCBANK",
        blockers_found=[hard],
        is_blocked=True,
    )
    assert report.is_blocked is True
    assert report.blockers_found[0].severity == "hard"


# --- Failure cases ---

def test_is_blocked_true_with_no_hard_blockers_rejected() -> None:
    """is_blocked=True requires at least one hard blocker."""
    soft = _detail(
        severity="soft", reason="Minor concern.", source_category="news_feed"
    )
    with pytest.raises(ValidationError, match="is_blocked must be False"):
        _report(
            symbol="TCS",
            blockers_found=[soft],
            is_blocked=True,
        )


def test_is_blocked_false_with_hard_blocker_rejected() -> None:
    """is_blocked=False is invalid when a hard blocker is present."""
    hard = _detail()
    with pytest.raises(ValidationError, match="is_blocked must be True"):
        _report(
            symbol="RELIANCE",
            blockers_found=[hard],
            is_blocked=False,
        )


def test_invalid_severity_rejected() -> None:
    with pytest.raises(ValidationError):
        BlockerDetail(
            category=BlockerCategory.OVERNIGHT_GAP,
            severity="medium",  # type: ignore[arg-type]
            reason="Gap risk present.",
            source_category="market_data",
        )


# --- Round-trip ---

def test_serialization_round_trip() -> None:
    hard = _detail(expires_at=_EXPIRY)
    report = _report(blockers_found=[hard], is_blocked=True)
    json_str = report.model_dump_json()
    restored = BlockerReport.model_validate_json(json_str)
    assert restored == report


# --- Schema export ---

def test_schema_export() -> None:
    schema = BlockerReport.model_json_schema()
    assert isinstance(schema, dict)
    assert schema["title"] == "BlockerReport"
    assert "properties" in schema
