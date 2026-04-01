"""Mock broker adapter — implements BrokerAdapter for shadow-live testing.

Always operates in dry_run mode. No real network calls. Every method
logs an AuditEvent so all interactions are observable in the audit ledger.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from packages.contracts.audit_event import AuditEvent
from packages.contracts.broker import (
    BrokerConfig,
    BrokerHealth,
    BrokerSession,
    OrderModification,
)
from packages.contracts.broker_config import Quote
from packages.contracts.enums import Mode, OrderStatus
from packages.contracts.order_intent import OrderIntent
from packages.contracts.order_state import OrderRecord, OrderStateTransition
from packages.contracts.portfolio import Position
from services.audit_ledger.ledger import AuditLedger

# Fixture prices for mock quotes (same symbols as Phase 2 universe)
_FIXTURE_PRICES: dict[str, Decimal] = {
    "RELIANCE": Decimal("2840.50"),
    "TCS": Decimal("3920.75"),
    "INFY": Decimal("1580.25"),
    "HDFCBANK": Decimal("1650.00"),
    "SBIN": Decimal("780.30"),
    "ICICIBANK": Decimal("1120.00"),
    "BHARTIARTL": Decimal("1240.50"),
    "ITC": Decimal("460.80"),
    "KOTAKBANK": Decimal("1780.00"),
    "AXISBANK": Decimal("1090.00"),
    "HINDUNILVR": Decimal("2350.00"),
    "MARUTI": Decimal("10250.00"),
    "TATAMOTORS": Decimal("620.50"),
    "SUNPHARMA": Decimal("1420.00"),
    "WIPRO": Decimal("450.00"),
    "TITAN": Decimal("3180.00"),
    "ULTRACEMCO": Decimal("9800.00"),
    "BAJFINANCE": Decimal("6540.00"),
    "NESTLEIND": Decimal("2480.00"),
    "ADANIENT": Decimal("2920.00"),
    "TECHM": Decimal("1280.00"),
    "POWERGRID": Decimal("290.00"),
    "NTPC": Decimal("340.00"),
    "ONGC": Decimal("265.00"),
    "LT": Decimal("3450.00"),
}


class MockBrokerAdapter:
    """Mock broker adapter for shadow-live testing.

    Implements the BrokerAdapter protocol. Always operates in dry_run mode.
    Every method logs an AuditEvent for full observability.
    """

    def __init__(
        self,
        config: BrokerConfig,
        audit_ledger: AuditLedger,
        mode: Mode = Mode.SHADOW_LIVE,
    ) -> None:
        self._config = config
        self._ledger = audit_ledger
        self._mode = mode
        self._session: BrokerSession | None = None

    async def _log_event(
        self,
        event_type: str,
        payload: dict[str, object],
        symbol: str | None = None,
        intent_id: str | None = None,
    ) -> None:
        """Record an audit event for a broker operation."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            event_type=event_type,
            source_service="mock_broker",
            mode=self._mode,
            payload=payload,
            related_symbol=symbol,
            related_intent_id=intent_id,
            operator_visible=True,
        )
        await self._ledger.record(event)

    async def authenticate(self) -> BrokerSession:
        """Return a valid mock session with 8-hour expiry."""
        now = datetime.now(UTC)
        self._session = BrokerSession(
            session_id=str(uuid.uuid4()),
            expires_at=now + timedelta(hours=8),
            broker_name=self._config.broker_name,
            is_live=not self._config.dry_run,
        )
        await self._log_event(
            "broker_authenticate",
            {
                "session_id": self._session.session_id,
                "broker_name": self._config.broker_name,
                "dry_run": self._config.dry_run,
            },
        )
        return self._session

    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Return fixture prices for requested symbols."""
        now = datetime.now(UTC)
        quotes: dict[str, Quote] = {}
        for sym in symbols:
            price = _FIXTURE_PRICES.get(sym, Decimal("1000.00"))
            quotes[sym] = Quote(
                symbol=sym,
                last_price=price,
                open=price,
                high=price * Decimal("1.02"),
                low=price * Decimal("0.98"),
                close=price,
                volume=100000,
                timestamp=now,
            )
        await self._log_event(
            "broker_get_quotes",
            {"symbols": symbols, "count": len(quotes)},
        )
        return quotes

    async def place_order(
        self, intent: OrderIntent, idempotency_key: str = ""
    ) -> OrderRecord:
        """Simulate order placement in dry-run mode.

        Critical: Always checks dry_run before doing anything. If dry_run=True,
        logs the intent as an AuditEvent and returns a simulated OrderRecord.
        NEVER makes a real network call regardless of any other state.
        """
        if not self._config.dry_run:
            raise RuntimeError(
                "MockBrokerAdapter must always run with dry_run=True. "
                "Refusing to place a real order."
            )

        order_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        # Simulate a fill at the fixture price
        fill_price = _FIXTURE_PRICES.get(
            intent.symbol, Decimal("1000.00")
        )

        transition_submit = OrderStateTransition(
            order_id=order_id,
            from_status=OrderStatus.PENDING,
            to_status=OrderStatus.SUBMITTED,
            timestamp=now,
            reason="dry_run_submit",
        )
        transition_fill = OrderStateTransition(
            order_id=order_id,
            from_status=OrderStatus.SUBMITTED,
            to_status=OrderStatus.FILLED,
            timestamp=now,
            reason="dry_run_simulated_fill",
            fill_price=fill_price,
            filled_qty=intent.quantity,
        )

        record = OrderRecord(
            order_id=order_id,
            intent=intent,
            current_status=OrderStatus.FILLED,
            submitted_at=now,
            filled_at=now,
            fill_price=fill_price,
            filled_qty=intent.quantity,
            remaining_qty=0,
            transitions=[transition_submit, transition_fill],
            created_at=now,
        )

        await self._log_event(
            "broker_place_order_dry_run",
            {
                "order_id": order_id,
                "symbol": intent.symbol,
                "side": intent.side.value,
                "quantity": intent.quantity,
                "fill_price": str(fill_price),
                "dry_run": True,
                "idempotency_key": idempotency_key,
            },
            symbol=intent.symbol,
            intent_id=intent.intent_id,
        )

        return record

    async def modify_order(
        self, order_id: str, modification: OrderModification
    ) -> OrderRecord:
        """Simulate order modification. Not supported in mock mode."""
        await self._log_event(
            "broker_modify_order",
            {
                "order_id": order_id,
                "modification": modification.model_dump(mode="json"),
                "dry_run": True,
            },
        )
        raise NotImplementedError("Order modification not supported in mock broker")

    async def cancel_order(self, order_id: str, reason: str) -> OrderRecord:
        """Simulate order cancellation. Not supported in mock mode."""
        await self._log_event(
            "broker_cancel_order",
            {"order_id": order_id, "reason": reason, "dry_run": True},
        )
        raise NotImplementedError("Order cancellation not supported in mock broker")

    async def get_positions(self) -> list[Position]:
        """Return empty list — no real positions in shadow mode."""
        await self._log_event(
            "broker_get_positions",
            {"count": 0, "dry_run": True},
        )
        return []

    async def get_orders(self, since: date | None = None) -> list[OrderRecord]:
        """Return empty list — no real orders in shadow mode."""
        await self._log_event(
            "broker_get_orders",
            {"since": since.isoformat() if since else None, "dry_run": True},
        )
        return []

    async def healthcheck(self) -> BrokerHealth:
        """Return healthy with fixed latency."""
        now = datetime.now(UTC)
        health = BrokerHealth(
            is_healthy=True,
            latency_ms=10,
            last_checked=now,
            session_valid=self._session is not None,
        )
        await self._log_event(
            "broker_healthcheck",
            {
                "is_healthy": True,
                "latency_ms": 10,
                "session_valid": self._session is not None,
            },
        )
        return health
