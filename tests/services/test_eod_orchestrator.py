"""Tests for the EOD orchestrator."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from packages.contracts.broker_config import PaperBrokerConfig
from packages.contracts.enums import Mode, OrderStatus
from services.audit_ledger.ledger import AuditLedger
from services.data_ingest.providers.fixture_provider import FixtureMarketDataProvider
from services.paper_broker.broker import PaperBroker
from services.paper_broker.eod_orchestrator import EODOrchestrator
from services.paper_broker.stop_manager import StopExitManager


@pytest.fixture
def orchestrator(tmp_path: Path) -> EODOrchestrator:
    data_provider = FixtureMarketDataProvider()
    broker = PaperBroker(
        PaperBrokerConfig(data_dir=tmp_path / "broker")
    )
    broker.set_cash(Decimal("10000000"))
    ledger = AuditLedger(tmp_path / "audit")
    stop_manager = StopExitManager(data_dir=tmp_path / "stops")
    return EODOrchestrator(
        data_provider=data_provider,
        paper_broker=broker,
        audit_ledger=ledger,
        stop_manager=stop_manager,
        universe_symbols=["RELIANCE", "TCS", "INFY", "HDFCBANK", "SBIN"],
    )


class TestEODOrchestrator:
    @pytest.mark.asyncio
    async def test_single_day_produces_valid_report(
        self, orchestrator: EODOrchestrator
    ) -> None:
        """Single day run with fixture data -> produces valid EODRunReport."""
        # Use a date that has data in fixtures (mid-range)
        report = await orchestrator.run_eod(date(2026, 1, 5))

        assert report.run_id is not None
        assert report.trading_date == date(2026, 1, 5)
        assert report.mode == Mode.PAPER
        assert report.started_at <= report.completed_at
        assert report.regime is not None
        assert report.portfolio_risk is not None
        assert report.reconciliation is not None

    @pytest.mark.asyncio
    async def test_run_produces_audit_events(
        self, orchestrator: EODOrchestrator
    ) -> None:
        """Run produces AuditEvents for each step."""
        await orchestrator.run_eod(date(2026, 1, 5))

        # Events are timestamped at UTC now, not simulated date
        from datetime import UTC
        from datetime import datetime as dt

        today_utc = dt.now(UTC).date()
        events = await orchestrator._ledger.get_events_for_date(today_utc)
        assert len(events) > 0

        # Should have step events
        event_types = {e.event_type for e in events}
        assert "eod_step_load_data" in event_types
        assert "eod_step_build_features" in event_types
        assert "eod_run_completed" in event_types

    @pytest.mark.asyncio
    async def test_entry_approved_order_submitted(
        self, orchestrator: EODOrchestrator
    ) -> None:
        """If entries are approved, orders are submitted with SUBMITTED status."""
        report = await orchestrator.run_eod(date(2026, 1, 5))

        if report.entries_approved > 0:
            submitted = await orchestrator._broker.get_orders(
                OrderStatus.SUBMITTED
            )
            assert len(submitted) > 0

    @pytest.mark.asyncio
    async def test_next_day_fills_previous_orders(
        self, orchestrator: EODOrchestrator
    ) -> None:
        """Next day run -> previous day's orders get filled."""
        # Day 1: may submit orders
        await orchestrator.run_eod(date(2026, 1, 5))
        submitted_count = len(
            await orchestrator._broker.get_orders(OrderStatus.SUBMITTED)
        )

        # Day 2: should fill day 1's orders
        report2 = await orchestrator.run_eod(date(2026, 1, 6))

        if submitted_count > 0:
            assert report2.orders_filled > 0

    @pytest.mark.asyncio
    async def test_report_includes_reconciliation(
        self, orchestrator: EODOrchestrator
    ) -> None:
        """Report includes reconciliation result."""
        report = await orchestrator.run_eod(date(2026, 1, 5))
        assert report.reconciliation is not None
        assert isinstance(report.reconciliation.is_clean, bool)

    @pytest.mark.asyncio
    async def test_error_in_step_doesnt_crash_run(
        self, orchestrator: EODOrchestrator
    ) -> None:
        """Error in one step doesn't crash the full run."""
        # Use a date with no data — some steps will fail gracefully
        report = await orchestrator.run_eod(date(2024, 1, 1))
        # Should still complete and return a report
        assert report.run_id is not None
        assert report.completed_at is not None
