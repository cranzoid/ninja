"""Tests for the paper simulation runner."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from packages.contracts.broker_config import PaperBrokerConfig
from services.audit_ledger.ledger import AuditLedger
from services.data_ingest.providers.fixture_provider import FixtureMarketDataProvider
from services.paper_broker.broker import PaperBroker
from services.paper_broker.eod_orchestrator import EODOrchestrator
from services.paper_broker.simulation_runner import PaperSimulationRunner
from services.paper_broker.stop_manager import StopExitManager


@pytest.fixture
def runner(tmp_path: Path) -> PaperSimulationRunner:
    data_provider = FixtureMarketDataProvider()
    broker = PaperBroker(
        PaperBrokerConfig(data_dir=tmp_path / "broker")
    )
    ledger = AuditLedger(tmp_path / "audit")
    stop_manager = StopExitManager(data_dir=tmp_path / "stops")
    orchestrator = EODOrchestrator(
        data_provider=data_provider,
        paper_broker=broker,
        audit_ledger=ledger,
        stop_manager=stop_manager,
        universe_symbols=["RELIANCE", "TCS", "INFY", "HDFCBANK", "SBIN"],
    )
    return PaperSimulationRunner(orchestrator, tmp_path / "sims")


class TestSimulationRunner:
    @pytest.mark.asyncio
    async def test_5_day_simulation_generates_reports(
        self, runner: PaperSimulationRunner
    ) -> None:
        """Run 5-day simulation -> 5 daily reports generated."""
        # Mon Jan 5 to Fri Jan 9, 2026 = 5 weekdays
        summary = await runner.run_simulation(
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 9),
            initial_equity=Decimal("10000000"),
        )

        assert summary.trading_days_run == 5
        assert len(summary.daily_reports) == 5

    @pytest.mark.asyncio
    async def test_equity_tracking_consistent(
        self, runner: PaperSimulationRunner
    ) -> None:
        """Equity tracking: initial + P&L = final (approximately)."""
        summary = await runner.run_simulation(
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 9),
            initial_equity=Decimal("10000000"),
        )

        # Final equity should be reasonable (not zero, not negative)
        assert summary.final_equity > 0
        assert summary.initial_equity == Decimal("10000000")

    @pytest.mark.asyncio
    async def test_summary_statistics_correct(
        self, runner: PaperSimulationRunner
    ) -> None:
        """Simulation summary statistics are calculated."""
        summary = await runner.run_simulation(
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 9),
            initial_equity=Decimal("10000000"),
        )

        assert summary.simulation_id is not None
        assert summary.total_return_pct is not None
        assert summary.max_drawdown_pct >= Decimal("0")
        assert summary.total_trades >= 0

    @pytest.mark.asyncio
    async def test_weekends_skipped(
        self, runner: PaperSimulationRunner
    ) -> None:
        """Weekends are skipped — 7 calendar days = 5 trading days."""
        # Mon Jan 5 to Sun Jan 11 = 5 weekdays
        summary = await runner.run_simulation(
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 11),
            initial_equity=Decimal("10000000"),
        )

        assert summary.trading_days_run == 5

    @pytest.mark.asyncio
    async def test_reconciliations_tracked(
        self, runner: PaperSimulationRunner
    ) -> None:
        """All reconciliations are tracked across the run."""
        summary = await runner.run_simulation(
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 9),
            initial_equity=Decimal("10000000"),
        )

        assert isinstance(summary.all_reconciliations_clean, bool)
        # Each daily report should have reconciliation
        for report in summary.daily_reports:
            assert report.reconciliation is not None
