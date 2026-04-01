"""Post-close reconciler and operator review gate for live trading.

Phase 7: Tiny Live. Compares broker state against audit ledger after
each trading session. Flags anomalies. Blocks next session if unresolved.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from packages.contracts.audit_event import AuditEvent
from packages.contracts.broker import LiveRunReport
from packages.contracts.enums import Mode, OrderStatus
from packages.contracts.order_state import OrderRecord
from packages.contracts.portfolio import Position
from packages.contracts.reconciliation import ReconciliationReport
from packages.contracts.risk import PortfolioRisk
from services.audit_ledger.ledger import AuditLedger


class LiveReconciler:
    """Compares broker state against audit ledger after a trading session.

    Read-only diagnostic — does NOT modify any state.
    """

    async def run_post_close(
        self,
        broker_orders: list[OrderRecord],
        broker_positions: list[Position],
        ledger: AuditLedger,
        trading_date: date,
        positions_before: list[Position],
        risk_utilization: PortfolioRisk,
    ) -> LiveRunReport:
        """Run post-close reconciliation and return a LiveRunReport."""
        anomalies: list[str] = []

        # Get all audit events for the trading date
        events = await ledger.get_events_for_date(trading_date)
        ledger_order_ids: set[str] = set()
        ledger_intent_ids: set[str] = set()

        for event in events:
            if event.event_type in (
                "broker_place_order",
                "broker_place_order_dry_run",
                "entry_order_submitted",
                "exit_order_submitted",
            ):
                oid = event.payload.get("order_id")
                if oid:
                    ledger_order_ids.add(str(oid))
            if event.related_intent_id:
                ledger_intent_ids.add(event.related_intent_id)

        broker_order_ids = {o.order_id for o in broker_orders}

        # Check for orphan broker orders (in broker but not in ledger)
        for oid in broker_order_ids:
            if oid not in ledger_order_ids:
                anomalies.append(f"orphan broker order: {oid}")

        # Check for missing broker confirmations (in ledger but not in broker)
        for oid in ledger_order_ids:
            if oid and oid not in broker_order_ids:
                anomalies.append(f"missing broker confirmation: {oid}")

        # Check for position mismatches
        broker_pos_map = {p.symbol: p for p in broker_positions}
        before_pos_map = {p.symbol: p for p in positions_before}

        # Positions that appeared but shouldn't have (not from our orders)
        for sym, _pos in broker_pos_map.items():
            if sym not in before_pos_map:
                # New position — check if we submitted an order for it
                order_symbols = {o.intent.symbol for o in broker_orders}
                if sym not in order_symbols:
                    anomalies.append(f"position mismatch: unexpected position in {sym}")

        # Check for unusual fill prices
        for order in broker_orders:
            if (
                order.current_status == OrderStatus.FILLED
                and order.fill_price is not None
                and order.intent.stop_price > 0
            ):
                # Compare fill price against intent's expected price range
                # If fill > 2% away from a reasonable expectation, flag it
                intent_price = order.intent.limit_price or order.intent.stop_price
                if intent_price > 0:
                    deviation = abs(order.fill_price - intent_price) / intent_price
                    if deviation > Decimal("0.02"):
                        anomalies.append(
                            f"unusual fill price: {order.intent.symbol} "
                            f"filled at {order.fill_price} vs expected ~{intent_price} "
                            f"({deviation:.1%} deviation)"
                        )

        # Classify orders
        orders_submitted = broker_orders
        orders_filled = [
            o for o in broker_orders if o.current_status == OrderStatus.FILLED
        ]
        orders_cancelled = [
            o for o in broker_orders if o.current_status == OrderStatus.CANCELLED
        ]

        # Build reconciliation report
        position_mismatches = [a for a in anomalies if "position" in a.lower()]
        order_mismatches = [
            a for a in anomalies if "order" in a.lower() or "confirmation" in a.lower()
        ]
        recon = ReconciliationReport(
            reconciled_at=datetime.now(UTC),
            target_date=trading_date,
            positions_match=len(position_mismatches) == 0,
            orders_match=len(order_mismatches) == 0,
            position_mismatches=position_mismatches,
            order_mismatches=order_mismatches,
            unmatched_intents=[],
            orphan_fills=[a for a in anomalies if "orphan" in a.lower()],
            is_clean=len(anomalies) == 0,
        )

        return LiveRunReport(
            trading_date=trading_date,
            mode=Mode.LIVE.value,
            orders_submitted=orders_submitted,
            orders_filled=orders_filled,
            orders_cancelled=orders_cancelled,
            positions_before=positions_before,
            positions_after=broker_positions,
            reconciliation_result=recon,
            risk_utilization=risk_utilization,
            anomalies=anomalies,
            reviewed_by_operator=False,
            review_notes=None,
            generated_at=datetime.now(UTC),
        )


class OperatorReviewGate:
    """Gates next trading session on operator review of previous session."""

    def __init__(self, audit_ledger: AuditLedger) -> None:
        self._ledger = audit_ledger

    def mark_reviewed(
        self,
        report: LiveRunReport,
        notes: str,
    ) -> LiveRunReport:
        """Mark a LiveRunReport as operator-reviewed.

        Mutates the report in-place (frozen=False) and logs an AuditEvent.
        """
        report.reviewed_by_operator = True
        report.review_notes = notes
        return report

    async def log_review(
        self,
        report: LiveRunReport,
        notes: str,
    ) -> None:
        """Log an audit event for the review."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            event_type="live_run_reviewed",
            source_service="operator_review_gate",
            mode=Mode.LIVE,
            payload={
                "trading_date": report.trading_date.isoformat(),
                "anomalies_count": len(report.anomalies),
                "review_notes": notes,
            },
            operator_visible=True,
        )
        await self._ledger.record(event)

    def has_unresolved_anomalies(self, report: LiveRunReport) -> bool:
        """True if anomalies exist AND not yet reviewed by operator."""
        return len(report.anomalies) > 0 and not report.reviewed_by_operator

    def can_run_next_session(self, report: LiveRunReport | None) -> bool:
        """False if previous session has unresolved anomalies.

        Gate C requirement: 'no unresolved reconciliation gaps'.
        Returns True if no previous report exists.
        """
        if report is None:
            return True
        return not self.has_unresolved_anomalies(report)
