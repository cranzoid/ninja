"""Phase 7 tests — LiveEODOrchestrator.

Tests the live orchestrator with mock broker — verifies environment guards,
operator review gates, and successful execution flow.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio

from packages.brokers.live_eod_orchestrator import LiveEODOrchestrator
from packages.brokers.live_reconciler import LiveReconciler, OperatorReviewGate
from packages.brokers.zerodha import ZerodhaAdapter
from packages.contracts.broker import BrokerConfig, LiveRunReport
from packages.contracts.enums import Mode
from packages.contracts.reconciliation import ReconciliationReport
from packages.contracts.risk import PortfolioRisk
from services.audit_ledger.ledger import AuditLedger
from services.data_ingest.providers.fixture_provider import FixtureMarketDataProvider


@pytest_asyncio.fixture
async def audit_ledger(tmp_path: Path) -> AuditLedger:
    return AuditLedger(tmp_path / "audit")


@pytest.fixture
def data_provider() -> FixtureMarketDataProvider:
    return FixtureMarketDataProvider()


@pytest.fixture
def broker_config() -> BrokerConfig:
    return BrokerConfig(
        broker_name="zerodha",
        base_url="https://mock-kite.test",
        timeout_seconds=5,
        max_retries=1,
        dry_run=True,  # Always dry-run in tests
    )


@pytest_asyncio.fixture
async def zerodha_adapter(
    broker_config: BrokerConfig, audit_ledger: AuditLedger
) -> ZerodhaAdapter:
    return ZerodhaAdapter(
        config=broker_config, audit_ledger=audit_ledger, mode=Mode.LIVE
    )


@pytest.fixture
def reconciler() -> LiveReconciler:
    return LiveReconciler()


@pytest.fixture
def review_gate(audit_ledger: AuditLedger) -> OperatorReviewGate:
    return OperatorReviewGate(audit_ledger=audit_ledger)


def _make_unresolved_report() -> LiveRunReport:
    """Create a LiveRunReport with unresolved anomalies."""
    return LiveRunReport(
        trading_date=date(2026, 3, 27),
        mode=Mode.LIVE.value,
        orders_submitted=[],
        orders_filled=[],
        orders_cancelled=[],
        positions_before=[],
        positions_after=[],
        reconciliation_result=ReconciliationReport(
            reconciled_at=datetime.now(UTC),
            target_date=date(2026, 3, 27),
            positions_match=True,
            orders_match=True,
            position_mismatches=[],
            order_mismatches=[],
            unmatched_intents=[],
            orphan_fills=[],
            is_clean=True,
        ),
        risk_utilization=PortfolioRisk(
            total_equity=Decimal("50000"),
            total_open_risk=Decimal("0"),
            open_risk_pct=Decimal("0"),
            position_count=0,
            sector_exposure={},
            largest_position_pct=Decimal("0"),
            is_within_limits=True,
            limit_breaches=[],
        ),
        anomalies=["orphan broker order: XYZ"],
        reviewed_by_operator=False,
        generated_at=datetime.now(UTC),
    )


class TestLiveEODOrchestrator:
    @pytest.mark.asyncio
    async def test_refuses_if_mode_not_live(
        self,
        data_provider: FixtureMarketDataProvider,
        zerodha_adapter: ZerodhaAdapter,
        audit_ledger: AuditLedger,
        reconciler: LiveReconciler,
        review_gate: OperatorReviewGate,
    ) -> None:
        """Refuses to run if MODE != live."""
        orchestrator = LiveEODOrchestrator(
            data_provider=data_provider,
            broker=zerodha_adapter,
            audit_ledger=audit_ledger,
            reconciler=reconciler,
            review_gate=review_gate,
        )

        with patch.dict(os.environ, {"MODE": "paper", "ARMED_LIVE": "true"}), \
             pytest.raises(RuntimeError, match="MODE=live"):
            await orchestrator.run_eod(date(2026, 3, 28))

    @pytest.mark.asyncio
    async def test_refuses_if_not_armed(
        self,
        data_provider: FixtureMarketDataProvider,
        zerodha_adapter: ZerodhaAdapter,
        audit_ledger: AuditLedger,
        reconciler: LiveReconciler,
        review_gate: OperatorReviewGate,
    ) -> None:
        """Refuses to run if ARMED_LIVE != true."""
        orchestrator = LiveEODOrchestrator(
            data_provider=data_provider,
            broker=zerodha_adapter,
            audit_ledger=audit_ledger,
            reconciler=reconciler,
            review_gate=review_gate,
        )

        with patch.dict(os.environ, {"MODE": "live", "ARMED_LIVE": "false"}), \
             pytest.raises(RuntimeError, match="ARMED_LIVE"):
            await orchestrator.run_eod(date(2026, 3, 28))

    @pytest.mark.asyncio
    async def test_refuses_if_unresolved_anomalies(
        self,
        data_provider: FixtureMarketDataProvider,
        zerodha_adapter: ZerodhaAdapter,
        audit_ledger: AuditLedger,
        reconciler: LiveReconciler,
        review_gate: OperatorReviewGate,
    ) -> None:
        """Refuses to run if previous session has unresolved anomalies."""
        unresolved = _make_unresolved_report()

        orchestrator = LiveEODOrchestrator(
            data_provider=data_provider,
            broker=zerodha_adapter,
            audit_ledger=audit_ledger,
            reconciler=reconciler,
            review_gate=review_gate,
            last_live_report=unresolved,
        )

        with patch.dict(os.environ, {"MODE": "live", "ARMED_LIVE": "true"}), \
             pytest.raises(RuntimeError, match="unresolved anomalies"):
            await orchestrator.run_eod(date(2026, 3, 28))

    @pytest.mark.asyncio
    async def test_completes_with_dry_run_broker(
        self,
        data_provider: FixtureMarketDataProvider,
        zerodha_adapter: ZerodhaAdapter,
        audit_ledger: AuditLedger,
        reconciler: LiveReconciler,
        review_gate: OperatorReviewGate,
    ) -> None:
        """Completes successfully with dry-run broker, returns LiveRunReport."""
        orchestrator = LiveEODOrchestrator(
            data_provider=data_provider,
            broker=zerodha_adapter,
            audit_ledger=audit_ledger,
            reconciler=reconciler,
            review_gate=review_gate,
        )

        with patch.dict(os.environ, {"MODE": "live", "ARMED_LIVE": "true"}):
            report = await orchestrator.run_eod(date(2026, 1, 5))

        assert isinstance(report, LiveRunReport)
        assert report.trading_date == date(2026, 1, 5)
        assert report.mode == Mode.LIVE.value
        assert report.generated_at is not None

    @pytest.mark.asyncio
    async def test_report_includes_reconciliation(
        self,
        data_provider: FixtureMarketDataProvider,
        zerodha_adapter: ZerodhaAdapter,
        audit_ledger: AuditLedger,
        reconciler: LiveReconciler,
        review_gate: OperatorReviewGate,
    ) -> None:
        """LiveRunReport includes ReconciliationReport."""
        orchestrator = LiveEODOrchestrator(
            data_provider=data_provider,
            broker=zerodha_adapter,
            audit_ledger=audit_ledger,
            reconciler=reconciler,
            review_gate=review_gate,
        )

        with patch.dict(os.environ, {"MODE": "live", "ARMED_LIVE": "true"}):
            report = await orchestrator.run_eod(date(2026, 1, 5))

        assert report.reconciliation_result is not None
        assert isinstance(report.reconciliation_result, ReconciliationReport)

    @pytest.mark.asyncio
    async def test_updates_last_report_reference(
        self,
        data_provider: FixtureMarketDataProvider,
        zerodha_adapter: ZerodhaAdapter,
        audit_ledger: AuditLedger,
        reconciler: LiveReconciler,
        review_gate: OperatorReviewGate,
    ) -> None:
        """After run_eod, the orchestrator's _last_report is updated."""
        orchestrator = LiveEODOrchestrator(
            data_provider=data_provider,
            broker=zerodha_adapter,
            audit_ledger=audit_ledger,
            reconciler=reconciler,
            review_gate=review_gate,
        )

        assert orchestrator._last_report is None

        with patch.dict(os.environ, {"MODE": "live", "ARMED_LIVE": "true"}):
            report = await orchestrator.run_eod(date(2026, 1, 5))

        assert orchestrator._last_report is report

    @pytest.mark.asyncio
    async def test_allows_run_after_review(
        self,
        data_provider: FixtureMarketDataProvider,
        zerodha_adapter: ZerodhaAdapter,
        audit_ledger: AuditLedger,
        reconciler: LiveReconciler,
        review_gate: OperatorReviewGate,
    ) -> None:
        """After reviewing anomalies, next session is allowed."""
        unresolved = _make_unresolved_report()
        review_gate.mark_reviewed(unresolved, "Reviewed and cleared")

        orchestrator = LiveEODOrchestrator(
            data_provider=data_provider,
            broker=zerodha_adapter,
            audit_ledger=audit_ledger,
            reconciler=reconciler,
            review_gate=review_gate,
            last_live_report=unresolved,
        )

        with patch.dict(os.environ, {"MODE": "live", "ARMED_LIVE": "true"}):
            report = await orchestrator.run_eod(date(2026, 1, 5))

        assert isinstance(report, LiveRunReport)

    @pytest.mark.asyncio
    async def test_audit_events_recorded(
        self,
        data_provider: FixtureMarketDataProvider,
        zerodha_adapter: ZerodhaAdapter,
        audit_ledger: AuditLedger,
        reconciler: LiveReconciler,
        review_gate: OperatorReviewGate,
    ) -> None:
        """Live EOD run records audit events."""
        orchestrator = LiveEODOrchestrator(
            data_provider=data_provider,
            broker=zerodha_adapter,
            audit_ledger=audit_ledger,
            reconciler=reconciler,
            review_gate=review_gate,
        )

        with patch.dict(os.environ, {"MODE": "live", "ARMED_LIVE": "true"}):
            await orchestrator.run_eod(date(2026, 1, 5))

        today = datetime.now(UTC).date()
        events = await audit_ledger.get_events_for_date(today)
        event_types = {e.event_type for e in events}

        assert "live_eod_step_load_data" in event_types
        assert "live_eod_run_completed" in event_types
