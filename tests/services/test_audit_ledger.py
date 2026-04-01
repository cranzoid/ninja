"""Tests for the audit ledger."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from packages.contracts.audit_event import AuditEvent
from packages.contracts.enums import Mode
from services.audit_ledger.ledger import AuditLedger


def _make_event(
    event_type: str = "order_filled",
    symbol: str | None = "RELIANCE",
    intent_id: str | None = None,
    timestamp: datetime | None = None,
) -> AuditEvent:
    return AuditEvent(
        event_id=str(uuid.uuid4()),
        timestamp=timestamp or datetime.now(UTC),
        event_type=event_type,
        source_service="paper_broker",
        mode=Mode.PAPER,
        payload={"test": True},
        related_symbol=symbol,
        related_intent_id=intent_id,
    )


@pytest.fixture
def ledger(tmp_path: Path) -> AuditLedger:
    return AuditLedger(tmp_path / "audit")


class TestAuditLedger:
    @pytest.mark.asyncio
    async def test_record_single_event_queryable(
        self, ledger: AuditLedger
    ) -> None:
        """Record single event -> queryable."""
        event = _make_event()
        await ledger.record(event)

        results = await ledger.query()
        assert len(results) == 1
        assert results[0].event_id == event.event_id

    @pytest.mark.asyncio
    async def test_record_batch_all_queryable(
        self, ledger: AuditLedger
    ) -> None:
        """Record batch -> all queryable."""
        events = [_make_event() for _ in range(5)]
        await ledger.record_batch(events)

        results = await ledger.query(limit=10)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_query_by_event_type(self, ledger: AuditLedger) -> None:
        """Query by event_type filters correctly."""
        await ledger.record(_make_event(event_type="order_filled"))
        await ledger.record(_make_event(event_type="order_submitted"))
        await ledger.record(_make_event(event_type="order_filled"))

        results = await ledger.query(event_types=["order_filled"])
        assert len(results) == 2
        assert all(r.event_type == "order_filled" for r in results)

    @pytest.mark.asyncio
    async def test_query_by_symbol(self, ledger: AuditLedger) -> None:
        """Query by symbol filters correctly."""
        await ledger.record(_make_event(symbol="RELIANCE"))
        await ledger.record(_make_event(symbol="TCS"))
        await ledger.record(_make_event(symbol="RELIANCE"))

        results = await ledger.query(symbol="TCS")
        assert len(results) == 1
        assert results[0].related_symbol == "TCS"

    @pytest.mark.asyncio
    async def test_query_by_date_range(self, ledger: AuditLedger) -> None:
        """Query by date range filters correctly."""
        t1 = datetime(2026, 3, 25, 10, 0, 0, tzinfo=UTC)
        t2 = datetime(2026, 3, 26, 10, 0, 0, tzinfo=UTC)
        t3 = datetime(2026, 3, 27, 10, 0, 0, tzinfo=UTC)

        await ledger.record(_make_event(timestamp=t1))
        await ledger.record(_make_event(timestamp=t2))
        await ledger.record(_make_event(timestamp=t3))

        results = await ledger.query(start_time=t2, end_time=t2 + timedelta(hours=23))
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_events_for_intent(self, ledger: AuditLedger) -> None:
        """get_events_for_intent returns linked events."""
        intent_id = str(uuid.uuid4())
        await ledger.record(_make_event(intent_id=intent_id))
        await ledger.record(_make_event(intent_id=None))
        await ledger.record(_make_event(intent_id=intent_id))

        results = await ledger.get_events_for_intent(intent_id)
        assert len(results) == 2
        assert all(r.related_intent_id == intent_id for r in results)

    @pytest.mark.asyncio
    async def test_ledger_survives_write_failure(
        self, ledger: AuditLedger
    ) -> None:
        """Ledger survives simulated write failure without crashing."""
        # Record one event normally
        event1 = _make_event()
        await ledger.record(event1)

        # Simulate write failure by making storage dir read-only temporarily
        with patch("builtins.open", side_effect=OSError("disk full")):
            # Should not raise — ledger logs the error and continues
            event2 = _make_event()
            await ledger.record(event2)

        # Original event is still queryable
        results = await ledger.query()
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_event_count(self, ledger: AuditLedger) -> None:
        """Event count returns correct total."""
        for _ in range(3):
            await ledger.record(_make_event())

        count = await ledger.event_count
        assert count == 3
