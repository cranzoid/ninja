"""Tests for the order state machine — the most critical Phase 3 component."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.contracts.enums import (
    ExecutionTiming,
    Mode,
    OrderSide,
    OrderStatus,
    OrderType,
    PortfolioLayer,
    RegimeClass,
)
from packages.contracts.exceptions import InvalidStateTransition
from packages.contracts.order_intent import OrderIntent
from services.paper_broker.state_machine import OrderStateMachine


def _make_intent(
    symbol: str = "RELIANCE",
    side: OrderSide = OrderSide.BUY,
    quantity: int = 10,
) -> OrderIntent:
    return OrderIntent(
        intent_id=str(uuid.uuid4()),
        symbol=symbol,
        layer=PortfolioLayer.SWING,
        side=side,
        order_type=OrderType.MARKET,
        quantity=quantity,
        stop_price=Decimal("2600.00"),
        risk_amount=Decimal("2000.00"),
        risk_pct_of_equity=Decimal("0.20"),
        execution_timing=ExecutionTiming.NEXT_OPEN,
        regime_at_intent=RegimeClass.GREEN,
        created_at=datetime.now(UTC),
        approved_by="rule_engine",
        mode=Mode.PAPER,
    )


class TestOrderStateMachine:
    def test_full_lifecycle_pending_submitted_filled(self) -> None:
        """Valid full lifecycle: PENDING -> SUBMITTED -> FILLED."""
        machine = OrderStateMachine(_make_intent())
        assert machine.current_status == OrderStatus.PENDING

        event = machine.submit()
        assert machine.current_status == OrderStatus.SUBMITTED
        assert event.event_type == "order_submitted"

        now = datetime.now(UTC)
        event = machine.fill(Decimal("2800.00"), 10, now)
        assert machine.current_status == OrderStatus.FILLED
        assert event.event_type == "order_filled"
        assert machine.is_terminal
        assert machine.record.fill_price == Decimal("2800.00")
        assert machine.record.filled_qty == 10
        assert machine.record.remaining_qty == 0

    def test_partial_fill_path(self) -> None:
        """Valid partial fill: PENDING -> SUBMITTED -> PARTIALLY_FILLED -> FILLED."""
        machine = OrderStateMachine(_make_intent(quantity=20))
        machine.submit()

        now = datetime.now(UTC)
        event = machine.partial_fill(Decimal("2800.00"), 10, now)
        assert machine.current_status == OrderStatus.PARTIALLY_FILLED
        assert event.event_type == "order_partially_filled"
        assert machine.record.filled_qty == 10
        assert machine.record.remaining_qty == 10

        event = machine.fill(Decimal("2810.00"), 10, now)
        assert machine.current_status == OrderStatus.FILLED
        assert machine.is_terminal
        assert machine.record.filled_qty == 20
        assert machine.record.remaining_qty == 0

    def test_cancellation_from_pending(self) -> None:
        """Valid cancellation: PENDING -> CANCELLED."""
        machine = OrderStateMachine(_make_intent())
        event = machine.cancel("operator_cancel")
        assert machine.current_status == OrderStatus.CANCELLED
        assert machine.is_terminal
        assert event.event_type == "order_cancelled"

    def test_cancellation_from_submitted(self) -> None:
        """Valid cancellation: SUBMITTED -> CANCELLED."""
        machine = OrderStateMachine(_make_intent())
        machine.submit()
        machine.cancel("market_conditions_changed")
        assert machine.current_status == OrderStatus.CANCELLED
        assert machine.is_terminal

    def test_rejection_from_submitted(self) -> None:
        """SUBMITTED -> REJECTED."""
        machine = OrderStateMachine(_make_intent())
        machine.submit()
        machine.reject("insufficient_margin")
        assert machine.current_status == OrderStatus.REJECTED
        assert machine.is_terminal

    def test_expiry_from_submitted(self) -> None:
        """SUBMITTED -> EXPIRED."""
        machine = OrderStateMachine(_make_intent())
        machine.submit()
        machine.expire("end_of_day")
        assert machine.current_status == OrderStatus.EXPIRED
        assert machine.is_terminal

    def test_invalid_transition_filled_to_submitted(self) -> None:
        """Invalid: FILLED -> SUBMITTED raises InvalidStateTransition."""
        machine = OrderStateMachine(_make_intent())
        machine.submit()
        machine.fill(Decimal("2800.00"), 10, datetime.now(UTC))
        with pytest.raises(InvalidStateTransition):
            machine.submit()

    def test_invalid_transition_cancelled_to_filled(self) -> None:
        """Invalid: CANCELLED -> FILLED raises InvalidStateTransition."""
        machine = OrderStateMachine(_make_intent())
        machine.cancel("test")
        with pytest.raises(InvalidStateTransition):
            machine.fill(Decimal("2800.00"), 10, datetime.now(UTC))

    def test_invalid_transition_rejected_to_anything(self) -> None:
        """Terminal state REJECTED allows no further transitions."""
        machine = OrderStateMachine(_make_intent())
        machine.submit()
        machine.reject("bad_order")
        with pytest.raises(InvalidStateTransition):
            machine.submit()
        with pytest.raises(InvalidStateTransition):
            machine.cancel("try_cancel")

    def test_every_transition_produces_audit_event(self) -> None:
        """Every transition produces an AuditEvent with correct event_type."""
        machine = OrderStateMachine(_make_intent())

        event1 = machine.submit()
        assert event1.event_type == "order_submitted"
        assert event1.related_symbol == "RELIANCE"
        assert event1.related_intent_id is not None

        event2 = machine.fill(Decimal("2800.00"), 10, datetime.now(UTC))
        assert event2.event_type == "order_filled"
        assert event2.payload["fill_price"] == "2800.00"
        assert event2.payload["filled_qty"] == 10

    def test_order_record_tracks_complete_history(self) -> None:
        """OrderRecord tracks all transitions in history."""
        machine = OrderStateMachine(_make_intent(quantity=20))
        machine.submit()
        machine.partial_fill(Decimal("2800.00"), 10, datetime.now(UTC))
        machine.fill(Decimal("2810.00"), 10, datetime.now(UTC))

        assert len(machine.history) == 3
        assert machine.history[0].to_status == OrderStatus.SUBMITTED
        assert machine.history[1].to_status == OrderStatus.PARTIALLY_FILLED
        assert machine.history[2].to_status == OrderStatus.FILLED

        record = machine.record
        assert record.order_id is not None
        assert len(record.transitions) == 3
        assert record.filled_at is not None

    def test_audit_event_has_correct_mode(self) -> None:
        """AuditEvent mode matches the intent's mode."""
        machine = OrderStateMachine(_make_intent())
        event = machine.submit()
        assert event.mode == Mode.PAPER
