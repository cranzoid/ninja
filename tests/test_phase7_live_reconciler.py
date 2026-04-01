"""Phase 7 tests — LiveReconciler and OperatorReviewGate.

Tests post-close reconciliation and the operator review workflow.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio

from packages.brokers.live_reconciler import LiveReconciler, OperatorReviewGate
from packages.contracts.audit_event import AuditEvent
from packages.contracts.broker import LiveRunReport
from packages.contracts.enums import (
    ExecutionTiming,
    Mode,
    OrderSide,
    OrderStatus,
    OrderType,
    PortfolioLayer,
    RegimeClass,
)
from packages.contracts.order_intent import OrderIntent
from packages.contracts.order_state import OrderRecord
from packages.contracts.portfolio import Position
from packages.contracts.reconciliation import ReconciliationReport
from packages.contracts.risk import PortfolioRisk
from services.audit_ledger.ledger import AuditLedger


def _make_intent(symbol: str = "RELIANCE") -> OrderIntent:
    return OrderIntent(
        intent_id=str(uuid.uuid4()),
        symbol=symbol,
        layer=PortfolioLayer.SWING,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
        stop_price=Decimal("2700.00"),
        risk_amount=Decimal("1400.00"),
        risk_pct_of_equity=Decimal("0.28"),
        execution_timing=ExecutionTiming.NEXT_OPEN,
        regime_at_intent=RegimeClass.GREEN,
        created_at=datetime.now(UTC),
        approved_by="rule_engine",
        mode=Mode.LIVE,
    )


def _make_order(
    order_id: str = "ORD001",
    symbol: str = "RELIANCE",
    status: OrderStatus = OrderStatus.FILLED,
    fill_price: Decimal | None = Decimal("2710.00"),
) -> OrderRecord:
    now = datetime.now(UTC)
    intent = _make_intent(symbol)
    return OrderRecord(
        order_id=order_id,
        intent=intent,
        current_status=status,
        submitted_at=now,
        filled_at=now if status == OrderStatus.FILLED else None,
        fill_price=fill_price if status == OrderStatus.FILLED else None,
        filled_qty=intent.quantity if status == OrderStatus.FILLED else 0,
        remaining_qty=0 if status == OrderStatus.FILLED else intent.quantity,
        transitions=[],
        created_at=now,
    )


def _make_position(symbol: str = "RELIANCE") -> Position:
    return Position(
        symbol=symbol,
        layer=PortfolioLayer.SWING,
        quantity=10,
        entry_price=Decimal("2800.00"),
        current_price=Decimal("2840.00"),
        stop_price=Decimal("2700.00"),
        risk_amount=Decimal("1400.00"),
        sector="Energy",
        entry_date=date.today(),
    )


def _make_risk() -> PortfolioRisk:
    return PortfolioRisk(
        total_equity=Decimal("50000"),
        total_open_risk=Decimal("1400"),
        open_risk_pct=Decimal("2.80"),
        position_count=1,
        sector_exposure={"Energy": Decimal("56.80")},
        largest_position_pct=Decimal("56.80"),
        is_within_limits=True,
        limit_breaches=[],
    )


@pytest_asyncio.fixture
async def audit_ledger(tmp_path: Path) -> AuditLedger:
    return AuditLedger(tmp_path / "audit")


@pytest.fixture
def reconciler() -> LiveReconciler:
    return LiveReconciler()


@pytest.fixture
def review_gate(audit_ledger: AuditLedger) -> OperatorReviewGate:
    return OperatorReviewGate(audit_ledger=audit_ledger)


class TestLiveReconciler:
    @pytest.mark.asyncio
    async def test_clean_session_empty_anomalies(
        self, reconciler: LiveReconciler, audit_ledger: AuditLedger
    ) -> None:
        """Clean session with matching orders -> empty anomalies."""
        order = _make_order("ORD001")
        trading_date = datetime.now(UTC).date()

        # Record matching audit event
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            event_type="broker_place_order",
            source_service="zerodha_adapter",
            mode=Mode.LIVE,
            payload={"order_id": "ORD001"},
            operator_visible=True,
        )
        await audit_ledger.record(event)

        report = await reconciler.run_post_close(
            broker_orders=[order],
            broker_positions=[_make_position()],
            ledger=audit_ledger,
            trading_date=trading_date,
            positions_before=[_make_position()],
            risk_utilization=_make_risk(),
        )

        assert isinstance(report, LiveRunReport)
        assert len(report.anomalies) == 0
        assert report.reconciliation_result.is_clean is True

    @pytest.mark.asyncio
    async def test_orphan_broker_order_detected(
        self, reconciler: LiveReconciler, audit_ledger: AuditLedger
    ) -> None:
        """Order in broker but not in ledger -> 'orphan broker order'."""
        order = _make_order("ORPHAN001")
        trading_date = datetime.now(UTC).date()

        # No audit events recorded — order is orphan
        report = await reconciler.run_post_close(
            broker_orders=[order],
            broker_positions=[],
            ledger=audit_ledger,
            trading_date=trading_date,
            positions_before=[],
            risk_utilization=_make_risk(),
        )

        assert any("orphan broker order" in a for a in report.anomalies)

    @pytest.mark.asyncio
    async def test_missing_broker_confirmation_detected(
        self, reconciler: LiveReconciler, audit_ledger: AuditLedger
    ) -> None:
        """Order in ledger but not in broker -> 'missing broker confirmation'."""
        trading_date = datetime.now(UTC).date()

        # Record an audit event for an order that doesn't exist in broker
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            event_type="broker_place_order",
            source_service="zerodha_adapter",
            mode=Mode.LIVE,
            payload={"order_id": "GHOST001"},
            operator_visible=True,
        )
        await audit_ledger.record(event)

        report = await reconciler.run_post_close(
            broker_orders=[],  # No broker orders
            broker_positions=[],
            ledger=audit_ledger,
            trading_date=trading_date,
            positions_before=[],
            risk_utilization=_make_risk(),
        )

        assert any("missing broker confirmation" in a for a in report.anomalies)

    @pytest.mark.asyncio
    async def test_position_mismatch_detected(
        self, reconciler: LiveReconciler, audit_ledger: AuditLedger
    ) -> None:
        """Position in broker not from our orders -> 'position mismatch'."""
        trading_date = datetime.now(UTC).date()

        # Position exists in broker but no orders were submitted for it
        unexpected_pos = _make_position("SURPRISE")

        report = await reconciler.run_post_close(
            broker_orders=[],  # No orders
            broker_positions=[unexpected_pos],
            ledger=audit_ledger,
            trading_date=trading_date,
            positions_before=[],  # Wasn't there before
            risk_utilization=_make_risk(),
        )

        assert any("position mismatch" in a for a in report.anomalies)

    @pytest.mark.asyncio
    async def test_unusual_fill_price_detected(
        self, reconciler: LiveReconciler, audit_ledger: AuditLedger
    ) -> None:
        """Fill price > 2% from expected -> 'unusual fill price'."""
        trading_date = datetime.now(UTC).date()

        # Order with fill price far from stop_price
        order = _make_order(
            "UNUSUAL001",
            fill_price=Decimal("3500.00"),  # Way off from stop_price 2700
        )

        # Record matching audit event
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            event_type="broker_place_order",
            source_service="zerodha_adapter",
            mode=Mode.LIVE,
            payload={"order_id": "UNUSUAL001"},
            operator_visible=True,
        )
        await audit_ledger.record(event)

        report = await reconciler.run_post_close(
            broker_orders=[order],
            broker_positions=[],
            ledger=audit_ledger,
            trading_date=trading_date,
            positions_before=[],
            risk_utilization=_make_risk(),
        )

        assert any("unusual fill price" in a for a in report.anomalies)

    @pytest.mark.asyncio
    async def test_report_includes_order_classifications(
        self, reconciler: LiveReconciler, audit_ledger: AuditLedger
    ) -> None:
        """Report correctly classifies filled vs cancelled orders."""
        trading_date = datetime.now(UTC).date()

        filled_order = _make_order("FILL001", status=OrderStatus.FILLED)
        cancelled_order = _make_order("CANCEL001", status=OrderStatus.CANCELLED)

        # Record audit events for both
        for oid in ["FILL001", "CANCEL001"]:
            event = AuditEvent(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC),
                event_type="broker_place_order",
                source_service="zerodha_adapter",
                mode=Mode.LIVE,
                payload={"order_id": oid},
                operator_visible=True,
            )
            await audit_ledger.record(event)

        report = await reconciler.run_post_close(
            broker_orders=[filled_order, cancelled_order],
            broker_positions=[],
            ledger=audit_ledger,
            trading_date=trading_date,
            positions_before=[],
            risk_utilization=_make_risk(),
        )

        assert len(report.orders_filled) == 1
        assert len(report.orders_cancelled) == 1


class TestOperatorReviewGate:
    def test_mark_reviewed_sets_flag(
        self, review_gate: OperatorReviewGate
    ) -> None:
        """mark_reviewed() sets reviewed_by_operator=True."""
        report = LiveRunReport(
            trading_date=date.today(),
            mode=Mode.LIVE.value,
            orders_submitted=[],
            orders_filled=[],
            orders_cancelled=[],
            positions_before=[],
            positions_after=[],
            reconciliation_result=ReconciliationReport(
                reconciled_at=datetime.now(UTC),
                target_date=date.today(),
                positions_match=True,
                orders_match=True,
                position_mismatches=[],
                order_mismatches=[],
                unmatched_intents=[],
                orphan_fills=[],
                is_clean=True,
            ),
            risk_utilization=_make_risk(),
            anomalies=["test anomaly"],
            generated_at=datetime.now(UTC),
        )

        assert not report.reviewed_by_operator
        result = review_gate.mark_reviewed(report, "All clear after manual check")
        assert result.reviewed_by_operator is True
        assert result.review_notes == "All clear after manual check"

    def test_has_unresolved_anomalies_true_when_not_reviewed(
        self, review_gate: OperatorReviewGate
    ) -> None:
        """has_unresolved_anomalies() True if anomalies exist and not reviewed."""
        report = LiveRunReport(
            trading_date=date.today(),
            mode=Mode.LIVE.value,
            orders_submitted=[],
            orders_filled=[],
            orders_cancelled=[],
            positions_before=[],
            positions_after=[],
            reconciliation_result=ReconciliationReport(
                reconciled_at=datetime.now(UTC),
                target_date=date.today(),
                positions_match=True,
                orders_match=True,
                position_mismatches=[],
                order_mismatches=[],
                unmatched_intents=[],
                orphan_fills=[],
                is_clean=True,
            ),
            risk_utilization=_make_risk(),
            anomalies=["orphan broker order: XYZ"],
            generated_at=datetime.now(UTC),
        )

        assert review_gate.has_unresolved_anomalies(report) is True

    def test_can_run_next_session_false_with_unresolved(
        self, review_gate: OperatorReviewGate
    ) -> None:
        """can_run_next_session() False if unresolved anomalies."""
        report = LiveRunReport(
            trading_date=date.today(),
            mode=Mode.LIVE.value,
            orders_submitted=[],
            orders_filled=[],
            orders_cancelled=[],
            positions_before=[],
            positions_after=[],
            reconciliation_result=ReconciliationReport(
                reconciled_at=datetime.now(UTC),
                target_date=date.today(),
                positions_match=True,
                orders_match=True,
                position_mismatches=[],
                order_mismatches=[],
                unmatched_intents=[],
                orphan_fills=[],
                is_clean=True,
            ),
            risk_utilization=_make_risk(),
            anomalies=["orphan order"],
            generated_at=datetime.now(UTC),
        )

        assert review_gate.can_run_next_session(report) is False

    def test_can_run_next_session_true_after_review(
        self, review_gate: OperatorReviewGate
    ) -> None:
        """can_run_next_session() True after mark_reviewed()."""
        report = LiveRunReport(
            trading_date=date.today(),
            mode=Mode.LIVE.value,
            orders_submitted=[],
            orders_filled=[],
            orders_cancelled=[],
            positions_before=[],
            positions_after=[],
            reconciliation_result=ReconciliationReport(
                reconciled_at=datetime.now(UTC),
                target_date=date.today(),
                positions_match=True,
                orders_match=True,
                position_mismatches=[],
                order_mismatches=[],
                unmatched_intents=[],
                orphan_fills=[],
                is_clean=True,
            ),
            risk_utilization=_make_risk(),
            anomalies=["test anomaly"],
            generated_at=datetime.now(UTC),
        )

        review_gate.mark_reviewed(report, "Reviewed and OK")
        assert review_gate.can_run_next_session(report) is True

    def test_can_run_next_session_true_when_no_report(
        self, review_gate: OperatorReviewGate
    ) -> None:
        """can_run_next_session() True when no previous report exists."""
        assert review_gate.can_run_next_session(None) is True

    @pytest.mark.asyncio
    async def test_mark_reviewed_logs_audit_event(
        self, review_gate: OperatorReviewGate, audit_ledger: AuditLedger
    ) -> None:
        """mark_reviewed() and log_review() logs AuditEvent."""
        report = LiveRunReport(
            trading_date=date.today(),
            mode=Mode.LIVE.value,
            orders_submitted=[],
            orders_filled=[],
            orders_cancelled=[],
            positions_before=[],
            positions_after=[],
            reconciliation_result=ReconciliationReport(
                reconciled_at=datetime.now(UTC),
                target_date=date.today(),
                positions_match=True,
                orders_match=True,
                position_mismatches=[],
                order_mismatches=[],
                unmatched_intents=[],
                orphan_fills=[],
                is_clean=True,
            ),
            risk_utilization=_make_risk(),
            anomalies=[],
            generated_at=datetime.now(UTC),
        )

        review_gate.mark_reviewed(report, "All good")
        await review_gate.log_review(report, "All good")

        today = datetime.now(UTC).date()
        events = await audit_ledger.get_events_for_date(today)
        review_events = [e for e in events if e.event_type == "live_run_reviewed"]
        assert len(review_events) >= 1
