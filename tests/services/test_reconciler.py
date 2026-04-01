"""Tests for the ledger reconciler."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from packages.contracts.audit_event import AuditEvent
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
from packages.contracts.order_state import OrderRecord, OrderStateTransition
from services.audit_ledger.ledger import AuditLedger
from services.audit_ledger.reconciler import LedgerReconciler


def _make_intent(symbol: str = "RELIANCE") -> OrderIntent:
    return OrderIntent(
        intent_id=str(uuid.uuid4()),
        symbol=symbol,
        layer=PortfolioLayer.SWING,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
        stop_price=Decimal("2600.00"),
        risk_amount=Decimal("2000.00"),
        risk_pct_of_equity=Decimal("0.20"),
        execution_timing=ExecutionTiming.NEXT_OPEN,
        regime_at_intent=RegimeClass.GREEN,
        created_at=datetime.now(UTC),
        approved_by="rule_engine",
        mode=Mode.PAPER,
    )


def _make_filled_order(
    order_id: str | None = None,
    intent: OrderIntent | None = None,
) -> OrderRecord:
    oid = order_id or str(uuid.uuid4())
    i = intent or _make_intent()
    now = datetime.now(UTC)
    return OrderRecord(
        order_id=oid,
        intent=i,
        current_status=OrderStatus.FILLED,
        submitted_at=now,
        filled_at=now,
        fill_price=Decimal("2800.00"),
        filled_qty=10,
        remaining_qty=0,
        transitions=[
            OrderStateTransition(
                order_id=oid,
                from_status=OrderStatus.PENDING,
                to_status=OrderStatus.SUBMITTED,
                timestamp=now,
            ),
            OrderStateTransition(
                order_id=oid,
                from_status=OrderStatus.SUBMITTED,
                to_status=OrderStatus.FILLED,
                timestamp=now,
                fill_price=Decimal("2800.00"),
                filled_qty=10,
            ),
        ],
        created_at=now,
    )


def _make_fill_event(
    order_id: str,
    symbol: str = "RELIANCE",
    target_date: date = date(2026, 1, 5),
) -> AuditEvent:
    return AuditEvent(
        event_id=str(uuid.uuid4()),
        timestamp=datetime(
            target_date.year, target_date.month, target_date.day,
            10, 0, tzinfo=UTC,
        ),
        event_type="order_filled",
        source_service="paper_broker",
        mode=Mode.PAPER,
        payload={
            "order_id": order_id,
            "symbol": symbol,
            "filled_qty": 10,
            "from_status": "submitted",
            "to_status": "filled",
        },
        related_symbol=symbol,
    )


@pytest.fixture
def ledger(tmp_path: Path) -> AuditLedger:
    return AuditLedger(tmp_path / "audit")


class TestReconciler:
    @pytest.mark.asyncio
    async def test_clean_state_is_clean(self, ledger: AuditLedger) -> None:
        """Clean state -> reconciliation is_clean = True."""
        order = _make_filled_order()
        await ledger.record(_make_fill_event(order.order_id))

        reconciler = LedgerReconciler()
        report = await reconciler.reconcile(
            broker_positions=[],
            broker_orders=[order],
            ledger=ledger,
            target_date=date(2026, 1, 5),
        )
        assert report.is_clean

    @pytest.mark.asyncio
    async def test_missing_fill_event_detected(
        self, ledger: AuditLedger
    ) -> None:
        """Order filled in broker but no fill event in ledger -> mismatch."""
        order = _make_filled_order()
        # Don't record a fill event in the ledger

        reconciler = LedgerReconciler()
        report = await reconciler.reconcile(
            broker_positions=[],
            broker_orders=[order],
            ledger=ledger,
            target_date=date(2026, 1, 5),
        )
        assert not report.orders_match
        assert len(report.order_mismatches) > 0

    @pytest.mark.asyncio
    async def test_orphan_fill_detected(self, ledger: AuditLedger) -> None:
        """Fill event in ledger without matching broker order -> orphan."""
        orphan_order_id = str(uuid.uuid4())
        await ledger.record(_make_fill_event(orphan_order_id))

        reconciler = LedgerReconciler()
        report = await reconciler.reconcile(
            broker_positions=[],
            broker_orders=[],  # No orders in broker
            ledger=ledger,
            target_date=date(2026, 1, 5),
        )
        assert not report.is_clean
        assert len(report.orphan_fills) > 0

    @pytest.mark.asyncio
    async def test_unmatched_intent_detected(
        self, ledger: AuditLedger
    ) -> None:
        """Intent in ledger without resulting order -> flagged."""
        intent_id = str(uuid.uuid4())
        await ledger.record(AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime(2026, 1, 5, 10, 0, tzinfo=UTC),
            event_type="order_intent_created",
            source_service="eod_orchestrator",
            mode=Mode.PAPER,
            payload={"intent_id": intent_id},
        ))

        reconciler = LedgerReconciler()
        report = await reconciler.reconcile(
            broker_positions=[],
            broker_orders=[],  # No orders
            ledger=ledger,
            target_date=date(2026, 1, 5),
        )
        assert not report.is_clean
        assert len(report.unmatched_intents) > 0
