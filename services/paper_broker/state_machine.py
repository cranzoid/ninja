"""Order state machine — manages the lifecycle of a single order.

Every transition is validated, timestamped, and produces an AuditEvent.
No shortcuts, no implicit transitions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from packages.contracts.audit_event import AuditEvent
from packages.contracts.enums import OrderStatus
from packages.contracts.exceptions import InvalidStateTransition
from packages.contracts.order_intent import OrderIntent
from packages.contracts.order_state import OrderRecord, OrderStateTransition

# Valid transitions: from_status -> set of allowed to_statuses
VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {
        OrderStatus.SUBMITTED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.SUBMITTED: {
        OrderStatus.FILLED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
    },
    OrderStatus.PARTIALLY_FILLED: {
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
    },
    # Terminal states — no further transitions allowed
    OrderStatus.FILLED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.REJECTED: set(),
    OrderStatus.EXPIRED: set(),
}

TERMINAL_STATES = {
    OrderStatus.FILLED,
    OrderStatus.CANCELLED,
    OrderStatus.REJECTED,
    OrderStatus.EXPIRED,
}


class OrderStateMachine:
    """
    Manages the lifecycle of a single order.
    Every transition is validated, timestamped, and produces an AuditEvent.
    """

    def __init__(self, order_intent: OrderIntent) -> None:
        now = datetime.now(UTC)
        self._record = OrderRecord(
            order_id=str(uuid.uuid4()),
            intent=order_intent,
            current_status=OrderStatus.PENDING,
            filled_qty=0,
            remaining_qty=order_intent.quantity,
            created_at=now,
        )
        self._transitions: list[OrderStateTransition] = []

    def _validate_transition(self, to_status: OrderStatus) -> None:
        current = self._record.current_status
        allowed = VALID_TRANSITIONS.get(current, set())
        if to_status not in allowed:
            raise InvalidStateTransition(
                from_status=current.value,
                to_status=to_status.value,
                reason=(
                    f"allowed from {current.value}: "
                    f"{sorted(s.value for s in allowed)}"
                    if allowed
                    else f"{current.value} is a terminal state"
                ),
            )

    def _apply_transition(
        self,
        to_status: OrderStatus,
        reason: str | None = None,
        fill_price: Decimal | None = None,
        filled_qty: int | None = None,
    ) -> AuditEvent:
        from_status = self._record.current_status
        self._validate_transition(to_status)

        now = datetime.now(UTC)
        transition = OrderStateTransition(
            order_id=self._record.order_id,
            from_status=from_status,
            to_status=to_status,
            timestamp=now,
            reason=reason,
            fill_price=fill_price,
            filled_qty=filled_qty,
        )
        self._transitions.append(transition)

        # Update record
        self._record.current_status = to_status
        self._record.transitions = list(self._transitions)

        if to_status == OrderStatus.SUBMITTED:
            self._record.submitted_at = now

        if filled_qty is not None and filled_qty > 0:
            self._record.filled_qty += filled_qty
            self._record.remaining_qty -= filled_qty

        if fill_price is not None:
            self._record.fill_price = fill_price

        if to_status == OrderStatus.FILLED:
            self._record.filled_at = now

        # Build event type based on transition
        event_type_map = {
            OrderStatus.SUBMITTED: "order_submitted",
            OrderStatus.FILLED: "order_filled",
            OrderStatus.PARTIALLY_FILLED: "order_partially_filled",
            OrderStatus.CANCELLED: "order_cancelled",
            OrderStatus.REJECTED: "order_rejected",
            OrderStatus.EXPIRED: "order_expired",
        }

        payload: dict[str, object] = {
            "order_id": self._record.order_id,
            "symbol": self._record.intent.symbol,
            "from_status": from_status.value,
            "to_status": to_status.value,
        }
        if reason:
            payload["reason"] = reason
        if fill_price is not None:
            payload["fill_price"] = str(fill_price)
        if filled_qty is not None:
            payload["filled_qty"] = filled_qty

        return AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=now,
            event_type=event_type_map.get(to_status, f"order_{to_status.value}"),
            source_service="paper_broker",
            mode=self._record.intent.mode,
            payload=payload,
            related_symbol=self._record.intent.symbol,
            related_intent_id=self._record.intent.intent_id,
            operator_visible=to_status in TERMINAL_STATES,
        )

    def submit(self) -> AuditEvent:
        """Transition from PENDING to SUBMITTED."""
        return self._apply_transition(OrderStatus.SUBMITTED)

    def fill(
        self,
        fill_price: Decimal,
        filled_qty: int,
        fill_timestamp: datetime,
    ) -> AuditEvent:
        """Transition to FILLED (complete fill)."""
        return self._apply_transition(
            OrderStatus.FILLED,
            fill_price=fill_price,
            filled_qty=filled_qty,
        )

    def partial_fill(
        self,
        fill_price: Decimal,
        filled_qty: int,
        fill_timestamp: datetime,
    ) -> AuditEvent:
        """Transition to PARTIALLY_FILLED."""
        return self._apply_transition(
            OrderStatus.PARTIALLY_FILLED,
            fill_price=fill_price,
            filled_qty=filled_qty,
        )

    def cancel(self, reason: str) -> AuditEvent:
        """Transition to CANCELLED."""
        return self._apply_transition(OrderStatus.CANCELLED, reason=reason)

    def reject(self, reason: str) -> AuditEvent:
        """Transition to REJECTED."""
        return self._apply_transition(OrderStatus.REJECTED, reason=reason)

    def expire(self, reason: str) -> AuditEvent:
        """Transition to EXPIRED."""
        return self._apply_transition(OrderStatus.EXPIRED, reason=reason)

    @property
    def current_status(self) -> OrderStatus:
        return self._record.current_status

    @property
    def is_terminal(self) -> bool:
        return self._record.current_status in TERMINAL_STATES

    @property
    def history(self) -> list[OrderStateTransition]:
        return list(self._transitions)

    @property
    def record(self) -> OrderRecord:
        return self._record
