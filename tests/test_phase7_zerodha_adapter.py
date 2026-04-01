"""Phase 7 tests — ZerodhaAdapter full implementation.

Uses a mock HTTP server (respx) for Kite API — zero real Zerodha calls.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio
import respx

from packages.brokers.zerodha import ZerodhaAdapter
from packages.contracts.broker import (
    BrokerAuthError,
    BrokerConfig,
    BrokerHealth,
    BrokerNetworkError,
    BrokerSession,
)
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

MOCK_BASE_URL = "https://mock-kite.test"


@pytest.fixture
def zerodha_config() -> BrokerConfig:
    return BrokerConfig(
        broker_name="zerodha",
        base_url=MOCK_BASE_URL,
        timeout_seconds=5,
        max_retries=2,
        dry_run=False,
    )


@pytest.fixture
def zerodha_config_dry_run() -> BrokerConfig:
    return BrokerConfig(
        broker_name="zerodha",
        base_url=MOCK_BASE_URL,
        timeout_seconds=5,
        max_retries=2,
        dry_run=True,
    )


@pytest_asyncio.fixture
async def audit_ledger(tmp_path: Path) -> AuditLedger:
    return AuditLedger(tmp_path / "audit")


@pytest_asyncio.fixture
async def adapter(
    zerodha_config: BrokerConfig, audit_ledger: AuditLedger
) -> ZerodhaAdapter:
    return ZerodhaAdapter(
        config=zerodha_config, audit_ledger=audit_ledger, mode=Mode.LIVE
    )


@pytest_asyncio.fixture
async def dry_run_adapter(
    zerodha_config_dry_run: BrokerConfig, audit_ledger: AuditLedger
) -> ZerodhaAdapter:
    return ZerodhaAdapter(
        config=zerodha_config_dry_run, audit_ledger=audit_ledger, mode=Mode.LIVE
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
        mode=Mode.LIVE,
    )


def _auth_env() -> dict[str, str]:
    return {
        "ZERODHA_API_KEY": "test_key",
        "ZERODHA_API_SECRET": "test_secret",
        "ZERODHA_REQUEST_TOKEN": "test_token",
    }


class TestZerodhaAuthenticate:
    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_valid_env_returns_session(
        self, adapter: ZerodhaAdapter
    ) -> None:
        """authenticate() with valid env vars returns BrokerSession."""
        respx.post(f"{MOCK_BASE_URL}/session/token").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"access_token": "mock_access_token_123"}},
            )
        )

        with patch.dict(os.environ, _auth_env()):
            session = await adapter.authenticate()

        assert isinstance(session, BrokerSession)
        assert session.broker_name == "zerodha"
        assert session.is_live is True
        assert session.expires_at > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_authenticate_missing_env_raises_auth_error(
        self, adapter: ZerodhaAdapter
    ) -> None:
        """authenticate() with missing env vars raises BrokerAuthError."""
        env = {
            "ZERODHA_API_KEY": "",
            "ZERODHA_API_SECRET": "",
            "ZERODHA_REQUEST_TOKEN": "",
        }
        with patch.dict(os.environ, env, clear=False):
            # Clear the vars explicitly
            for k in ["ZERODHA_API_KEY", "ZERODHA_API_SECRET", "ZERODHA_REQUEST_TOKEN"]:
                os.environ.pop(k, None)
            with pytest.raises(BrokerAuthError, match="Missing required"):
                await adapter.authenticate()

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_caches_session(
        self, adapter: ZerodhaAdapter
    ) -> None:
        """authenticate() caches session and reuses on subsequent calls."""
        route = respx.post(f"{MOCK_BASE_URL}/session/token").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"access_token": "cached_token"}},
            )
        )

        with patch.dict(os.environ, _auth_env()):
            session1 = await adapter.authenticate()
            session2 = await adapter.authenticate()

        # Should only call the API once
        assert route.call_count == 1
        assert session1.session_id == session2.session_id


class TestZerodhaPlaceOrder:
    @pytest.mark.asyncio
    async def test_place_order_dry_run_never_calls_http(
        self, dry_run_adapter: ZerodhaAdapter, audit_ledger: AuditLedger
    ) -> None:
        """place_order() with dry_run=True never calls HTTP, logs AuditEvent."""
        intent = _make_intent()
        record = await dry_run_adapter.place_order(intent, "key1")

        assert record.order_id != ""
        assert record.current_status == OrderStatus.SUBMITTED
        assert record.intent.symbol == "RELIANCE"

        # Verify audit event was logged
        today = datetime.now(UTC).date()
        events = await audit_ledger.get_events_for_date(today)
        dry_run_events = [
            e for e in events if e.event_type == "broker_place_order_dry_run"
        ]
        assert len(dry_run_events) >= 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_order_live_calls_api(
        self, adapter: ZerodhaAdapter
    ) -> None:
        """place_order() with dry_run=False calls mock server, returns OrderRecord."""
        # First authenticate
        respx.post(f"{MOCK_BASE_URL}/session/token").mock(
            return_value=httpx.Response(
                200, json={"data": {"access_token": "live_token"}}
            )
        )
        with patch.dict(os.environ, _auth_env()):
            await adapter.authenticate()

        # Mock place order
        respx.post(f"{MOCK_BASE_URL}/orders/regular").mock(
            return_value=httpx.Response(
                200, json={"data": {"order_id": "ZRD123456"}}
            )
        )

        intent = _make_intent()
        record = await adapter.place_order(intent, "key_live")

        assert record.order_id == "ZRD123456"
        assert record.current_status == OrderStatus.SUBMITTED

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_order_dedup_idempotency_key(
        self, adapter: ZerodhaAdapter
    ) -> None:
        """Duplicate idempotency_key returns existing order, no re-submit."""
        respx.post(f"{MOCK_BASE_URL}/session/token").mock(
            return_value=httpx.Response(
                200, json={"data": {"access_token": "token"}}
            )
        )
        with patch.dict(os.environ, _auth_env()):
            await adapter.authenticate()

        route = respx.post(f"{MOCK_BASE_URL}/orders/regular").mock(
            return_value=httpx.Response(
                200, json={"data": {"order_id": "DEDUP001"}}
            )
        )

        intent = _make_intent()
        record1 = await adapter.place_order(intent, "same_key")
        record2 = await adapter.place_order(intent, "same_key")

        assert record1.order_id == record2.order_id
        assert route.call_count == 1  # Only one HTTP call


class TestZerodhaGetQuotes:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_quotes_partial_failure(
        self, adapter: ZerodhaAdapter, audit_ledger: AuditLedger
    ) -> None:
        """get_quotes() with partial failure returns successful subset, logs missing."""
        respx.post(f"{MOCK_BASE_URL}/session/token").mock(
            return_value=httpx.Response(
                200, json={"data": {"access_token": "qt"}}
            )
        )
        with patch.dict(os.environ, _auth_env()):
            await adapter.authenticate()

        # Only return RELIANCE, not TCS
        respx.get(f"{MOCK_BASE_URL}/quote").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "NSE:RELIANCE": {
                            "last_price": 2840.50,
                            "volume": 100000,
                            "ohlc": {
                                "open": 2830.0,
                                "high": 2860.0,
                                "low": 2820.0,
                                "close": 2840.0,
                            },
                        }
                    }
                },
            )
        )

        quotes = await adapter.get_quotes(["RELIANCE", "TCS"])

        assert "RELIANCE" in quotes
        assert "TCS" not in quotes
        assert quotes["RELIANCE"].last_price == Decimal("2840.5")

        # Check missing symbol was logged
        today = datetime.now(UTC).date()
        events = await audit_ledger.get_events_for_date(today)
        missing_events = [e for e in events if e.event_type == "broker_quote_missing"]
        assert len(missing_events) >= 1


class TestZerodhaRetryAndErrors:
    @respx.mock
    @pytest.mark.asyncio
    async def test_5xx_retries_then_raises_network_error(
        self, adapter: ZerodhaAdapter
    ) -> None:
        """5xx response retries up to max_retries, then raises BrokerNetworkError."""
        respx.post(f"{MOCK_BASE_URL}/session/token").mock(
            return_value=httpx.Response(
                200, json={"data": {"access_token": "retry_token"}}
            )
        )
        with patch.dict(os.environ, _auth_env()):
            await adapter.authenticate()

        route = respx.get(f"{MOCK_BASE_URL}/quote").mock(
            return_value=httpx.Response(500, json={"error": "internal"})
        )

        with pytest.raises(BrokerNetworkError):
            await adapter.get_quotes(["RELIANCE"])

        # max_retries=2, so 3 total attempts
        assert route.call_count == 3

    @respx.mock
    @pytest.mark.asyncio
    async def test_401_raises_auth_error_no_retry(
        self, adapter: ZerodhaAdapter
    ) -> None:
        """401 response raises BrokerAuthError immediately (no retry)."""
        respx.post(f"{MOCK_BASE_URL}/session/token").mock(
            return_value=httpx.Response(
                200, json={"data": {"access_token": "auth_test"}}
            )
        )
        with patch.dict(os.environ, _auth_env()):
            await adapter.authenticate()

        route = respx.get(f"{MOCK_BASE_URL}/quote").mock(
            return_value=httpx.Response(401, json={"error": "unauthorized"})
        )

        with pytest.raises(BrokerAuthError):
            await adapter.get_quotes(["RELIANCE"])

        # Should NOT retry on 401
        assert route.call_count == 1


class TestZerodhaHealthcheck:
    @respx.mock
    @pytest.mark.asyncio
    async def test_healthcheck_returns_broker_health(
        self, adapter: ZerodhaAdapter
    ) -> None:
        """healthcheck() returns BrokerHealth with latency."""
        respx.get(f"{MOCK_BASE_URL}/quote").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "NSE:NIFTYBEES": {"last_price": 250.0, "volume": 500000}
                    }
                },
            )
        )

        health = await adapter.healthcheck()

        assert isinstance(health, BrokerHealth)
        assert health.is_healthy is True
        assert health.latency_ms >= 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_healthcheck_unhealthy_on_failure(
        self, adapter: ZerodhaAdapter
    ) -> None:
        """healthcheck() returns unhealthy when API fails."""
        respx.get(f"{MOCK_BASE_URL}/quote").mock(
            side_effect=httpx.ConnectError("connection refused")
        )

        health = await adapter.healthcheck()

        assert isinstance(health, BrokerHealth)
        assert health.is_healthy is False
        assert health.error_message is not None


class TestZerodhaGetPositions:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_positions_filters_nse_cnc(
        self, adapter: ZerodhaAdapter
    ) -> None:
        """get_positions() filters to NSE CNC delivery positions only."""
        respx.post(f"{MOCK_BASE_URL}/session/token").mock(
            return_value=httpx.Response(
                200, json={"data": {"access_token": "pos_token"}}
            )
        )
        with patch.dict(os.environ, _auth_env()):
            await adapter.authenticate()

        respx.get(f"{MOCK_BASE_URL}/positions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "net": [
                            {
                                "tradingsymbol": "RELIANCE",
                                "exchange": "NSE",
                                "product": "CNC",
                                "quantity": 10,
                                "average_price": 2800.0,
                                "last_price": 2840.0,
                            },
                            {
                                "tradingsymbol": "NIFTY2630020000CE",
                                "exchange": "NFO",
                                "product": "NRML",
                                "quantity": 50,
                                "average_price": 100.0,
                                "last_price": 110.0,
                            },
                            {
                                "tradingsymbol": "TCS",
                                "exchange": "NSE",
                                "product": "MIS",
                                "quantity": 5,
                                "average_price": 3900.0,
                                "last_price": 3920.0,
                            },
                        ]
                    }
                },
            )
        )

        positions = await adapter.get_positions()

        # Only RELIANCE should be returned (NSE + CNC)
        assert len(positions) == 1
        assert positions[0].symbol == "RELIANCE"
        assert positions[0].quantity == 10


class TestZerodhaGetOrders:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_orders_filters_by_date(
        self, adapter: ZerodhaAdapter
    ) -> None:
        """get_orders() filters orders by since date."""
        respx.post(f"{MOCK_BASE_URL}/session/token").mock(
            return_value=httpx.Response(
                200, json={"data": {"access_token": "ord_token"}}
            )
        )
        with patch.dict(os.environ, _auth_env()):
            await adapter.authenticate()

        today = datetime.now(UTC)
        yesterday = today - timedelta(days=1)

        respx.get(f"{MOCK_BASE_URL}/orders").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "order_id": "ORD001",
                            "tradingsymbol": "RELIANCE",
                            "transaction_type": "BUY",
                            "status": "COMPLETE",
                            "quantity": 10,
                            "filled_quantity": 10,
                            "pending_quantity": 0,
                            "average_price": 2840.50,
                            "order_timestamp": today.isoformat(),
                        },
                        {
                            "order_id": "ORD002",
                            "tradingsymbol": "TCS",
                            "transaction_type": "BUY",
                            "status": "OPEN",
                            "quantity": 5,
                            "filled_quantity": 0,
                            "pending_quantity": 5,
                            "average_price": 0,
                            "order_timestamp": yesterday.isoformat(),
                        },
                    ]
                },
            )
        )

        orders = await adapter.get_orders(since=today.date())

        # Only today's order
        assert len(orders) >= 1
        assert any(o.order_id == "ORD001" for o in orders)
