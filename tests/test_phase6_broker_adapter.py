"""Phase 6 tests — broker adapter contracts and mock/zerodha adapters.

Uses MockBrokerAdapter for all broker calls — no real broker in tests.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from pydantic import ValidationError

from packages.brokers.mock_broker import MockBrokerAdapter
from packages.brokers.zerodha import ZerodhaAdapter
from packages.contracts.broker import (
    BrokerAuthError,
    BrokerConfig,
    BrokerHealth,
    BrokerSession,
    OrderModification,
)
from packages.contracts.broker_config import Quote
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
from services.audit_ledger.ledger import AuditLedger


@pytest.fixture
def broker_config() -> BrokerConfig:
    return BrokerConfig(
        broker_name="mock",
        base_url="http://localhost",
        dry_run=True,
    )


@pytest_asyncio.fixture
async def audit_ledger(tmp_path: Path) -> AuditLedger:
    return AuditLedger(tmp_path / "audit")


@pytest_asyncio.fixture
async def mock_broker(
    broker_config: BrokerConfig, audit_ledger: AuditLedger
) -> MockBrokerAdapter:
    return MockBrokerAdapter(
        config=broker_config, audit_ledger=audit_ledger
    )


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
        mode=Mode.PAPER,
    )


class TestMockBrokerAdapter:
    """Tests for MockBrokerAdapter."""

    @pytest.mark.asyncio
    async def test_authenticate_returns_valid_session(
        self, mock_broker: MockBrokerAdapter
    ) -> None:
        session = await mock_broker.authenticate()
        assert isinstance(session, BrokerSession)
        assert session.broker_name == "mock"
        assert session.is_live is False
        assert session.expires_at > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_authenticate_session_8_hour_expiry(
        self, mock_broker: MockBrokerAdapter
    ) -> None:
        session = await mock_broker.authenticate()
        # Should be approximately 8 hours from now
        now = datetime.now(UTC)
        delta = session.expires_at - now
        assert timedelta(hours=7, minutes=59) < delta < timedelta(hours=8, minutes=1)

    @pytest.mark.asyncio
    async def test_place_order_dry_run_logs_audit_event(
        self, mock_broker: MockBrokerAdapter, audit_ledger: AuditLedger
    ) -> None:
        intent = _make_intent()
        record = await mock_broker.place_order(intent)

        assert record.current_status == OrderStatus.FILLED
        assert record.fill_price is not None
        assert record.filled_qty == intent.quantity

        # Verify audit event was logged
        from datetime import UTC
        today_utc = datetime.now(UTC).date()
        events = await audit_ledger.get_events_for_date(today_utc)
        order_events = [
            e for e in events if e.event_type == "broker_place_order_dry_run"
        ]
        assert len(order_events) >= 1

    @pytest.mark.asyncio
    async def test_place_order_dry_run_never_makes_network_call(
        self, mock_broker: MockBrokerAdapter
    ) -> None:
        """place_order with dry_run=True must never make a real network call."""
        intent = _make_intent()
        # This should complete without any network access
        record = await mock_broker.place_order(intent)
        assert record.current_status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_place_order_rejects_if_dry_run_false(
        self, audit_ledger: AuditLedger
    ) -> None:
        """MockBrokerAdapter must refuse to place real orders."""
        config = BrokerConfig(
            broker_name="mock",
            base_url="http://localhost",
            dry_run=False,
        )
        broker = MockBrokerAdapter(
            config=config, audit_ledger=audit_ledger
        )
        intent = _make_intent()
        with pytest.raises(RuntimeError, match="dry_run=True"):
            await broker.place_order(intent)

    @pytest.mark.asyncio
    async def test_healthcheck_returns_broker_health(
        self, mock_broker: MockBrokerAdapter
    ) -> None:
        health = await mock_broker.healthcheck()
        assert isinstance(health, BrokerHealth)
        assert health.is_healthy is True
        assert health.latency_ms == 10

    @pytest.mark.asyncio
    async def test_get_positions_returns_empty(
        self, mock_broker: MockBrokerAdapter
    ) -> None:
        positions = await mock_broker.get_positions()
        assert positions == []

    @pytest.mark.asyncio
    async def test_get_orders_returns_empty(
        self, mock_broker: MockBrokerAdapter
    ) -> None:
        orders = await mock_broker.get_orders()
        assert orders == []

    @pytest.mark.asyncio
    async def test_get_quotes_returns_fixture_prices(
        self, mock_broker: MockBrokerAdapter
    ) -> None:
        quotes = await mock_broker.get_quotes(["RELIANCE", "TCS"])
        assert "RELIANCE" in quotes
        assert "TCS" in quotes
        assert isinstance(quotes["RELIANCE"], Quote)
        assert quotes["RELIANCE"].last_price > 0

    @pytest.mark.asyncio
    async def test_every_method_logs_audit_event(
        self, mock_broker: MockBrokerAdapter, audit_ledger: AuditLedger
    ) -> None:
        """Every broker method should produce an audit event."""
        await mock_broker.authenticate()
        await mock_broker.healthcheck()
        await mock_broker.get_positions()
        await mock_broker.get_quotes(["RELIANCE"])

        from datetime import UTC
        today_utc = datetime.now(UTC).date()
        events = await audit_ledger.get_events_for_date(today_utc)
        event_types = {e.event_type for e in events}
        assert "broker_authenticate" in event_types
        assert "broker_healthcheck" in event_types
        assert "broker_get_positions" in event_types
        assert "broker_get_quotes" in event_types


class TestBrokerSessionContract:
    """Tests for BrokerSession Pydantic contract."""

    def test_valid_session(self) -> None:
        session = BrokerSession(
            session_id="test-123",
            expires_at=datetime.now(UTC) + timedelta(hours=8),
            broker_name="mock",
            is_live=False,
        )
        assert session.session_id == "test-123"
        assert session.broker_name == "mock"

    def test_session_is_frozen(self) -> None:
        session = BrokerSession(
            session_id="test-123",
            expires_at=datetime.now(UTC),
            broker_name="mock",
            is_live=False,
        )
        with pytest.raises(ValidationError):
            session.session_id = "changed"


class TestZerodhaAdapter:
    """Tests for ZerodhaAdapter stub."""

    @pytest.mark.asyncio
    async def test_authenticate_raises_if_env_vars_missing(
        self, tmp_path: Path
    ) -> None:
        config = BrokerConfig(
            broker_name="zerodha",
            base_url="https://api.kite.trade",
            dry_run=True,
        )
        ledger = AuditLedger(tmp_path / "audit")
        adapter = ZerodhaAdapter(config, audit_ledger=ledger)

        # Ensure env vars are not set
        env = os.environ.copy()
        os.environ.pop("ZERODHA_API_KEY", None)
        os.environ.pop("ZERODHA_API_SECRET", None)

        try:
            with pytest.raises(BrokerAuthError, match="Missing required"):
                await adapter.authenticate()
        finally:
            os.environ.update(env)

    @pytest.mark.asyncio
    async def test_authenticate_succeeds_with_env_vars(
        self, tmp_path: Path
    ) -> None:
        import respx

        config = BrokerConfig(
            broker_name="zerodha",
            base_url="https://mock-kite.test",
            dry_run=True,
        )
        ledger = AuditLedger(tmp_path / "audit")
        adapter = ZerodhaAdapter(config, audit_ledger=ledger)

        os.environ["ZERODHA_API_KEY"] = "test_key"
        os.environ["ZERODHA_API_SECRET"] = "test_secret"
        os.environ["ZERODHA_REQUEST_TOKEN"] = "test_token"

        try:
            with respx.mock:
                respx.post("https://mock-kite.test/session/token").mock(
                    return_value=httpx.Response(
                        200,
                        json={
                            "status": "success",
                            "data": {"access_token": "tok123"},
                        },
                    )
                )
                session = await adapter.authenticate()
            assert isinstance(session, BrokerSession)
            assert session.broker_name == "zerodha"
        finally:
            os.environ.pop("ZERODHA_API_KEY", None)
            os.environ.pop("ZERODHA_API_SECRET", None)
            os.environ.pop("ZERODHA_REQUEST_TOKEN", None)

    @pytest.mark.asyncio
    async def test_healthcheck_returns_health(
        self, tmp_path: Path
    ) -> None:
        config = BrokerConfig(
            broker_name="zerodha",
            base_url="https://api.kite.trade",
            dry_run=True,
        )
        ledger = AuditLedger(tmp_path / "audit")
        adapter = ZerodhaAdapter(config, audit_ledger=ledger)
        health = await adapter.healthcheck()
        assert isinstance(health, BrokerHealth)


class TestOrderModificationContract:
    """Tests for OrderModification contract."""

    def test_valid_modification(self) -> None:
        mod = OrderModification(
            order_id="order-123",
            new_quantity=5,
            reason="Reduce size per operator override",
        )
        assert mod.order_id == "order-123"

    def test_empty_reason_rejected(self) -> None:
        with pytest.raises(Exception, match="reason must not be empty"):
            OrderModification(
                order_id="order-123",
                reason="   ",
            )
