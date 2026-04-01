"""Tests for the paper broker."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from packages.contracts.broker_config import PaperBrokerConfig
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
from services.paper_broker.broker import PaperBroker


def _make_intent(
    symbol: str = "RELIANCE",
    side: OrderSide = OrderSide.BUY,
    quantity: int = 10,
    stop_price: Decimal = Decimal("2600.00"),
) -> OrderIntent:
    return OrderIntent(
        intent_id=str(uuid.uuid4()),
        symbol=symbol,
        layer=PortfolioLayer.SWING,
        side=side,
        order_type=OrderType.MARKET,
        quantity=quantity,
        stop_price=stop_price,
        risk_amount=Decimal("2000.00"),
        risk_pct_of_equity=Decimal("0.20"),
        execution_timing=ExecutionTiming.NEXT_OPEN,
        regime_at_intent=RegimeClass.GREEN,
        created_at=datetime.now(UTC),
        approved_by="rule_engine",
        mode=Mode.PAPER,
    )


def _make_market_data(
    symbol: str = "RELIANCE",
    target_date: date = date(2026, 1, 5),
    open_price: float = 2800.0,
) -> dict[str, pd.DataFrame]:
    return {
        symbol: pd.DataFrame([{
            "date": target_date,
            "open": open_price,
            "high": open_price + 50,
            "low": open_price - 50,
            "close": open_price + 10,
            "volume": 10_000_000,
        }])
    }


@pytest.fixture
def broker(tmp_path: Path) -> PaperBroker:
    config = PaperBrokerConfig(data_dir=tmp_path / "broker_data")
    b = PaperBroker(config)
    b.set_cash(Decimal("10000000"))
    return b


class TestPaperBroker:
    @pytest.mark.asyncio
    async def test_place_order_pending_then_submitted(
        self, broker: PaperBroker
    ) -> None:
        """Place order -> status is SUBMITTED (auto-submitted on place)."""
        intent = _make_intent()
        record = await broker.place_order(intent)
        assert record.current_status == OrderStatus.SUBMITTED
        assert record.intent.symbol == "RELIANCE"

    @pytest.mark.asyncio
    async def test_simulate_fills_correct_slippage(
        self, broker: PaperBroker
    ) -> None:
        """Simulate fills with known price data -> correct fill price with slippage."""
        intent = _make_intent()
        await broker.place_order(intent)

        market_data = _make_market_data(open_price=2800.0)
        events = await broker.simulate_fills(
            market_data, date(2026, 1, 5)
        )

        assert len(events) == 1
        # BUY slippage: 2800 * (1 + 5/10000) = 2800 * 1.0005 = 2801.40
        filled_order = (await broker.get_orders(OrderStatus.FILLED))[0]
        expected_price = Decimal("2800") * (1 + Decimal("5") / Decimal("10000"))
        assert filled_order.fill_price == expected_price.quantize(Decimal("0.01"))

    @pytest.mark.asyncio
    async def test_buy_fill_creates_position(self, broker: PaperBroker) -> None:
        """BUY fill creates/updates position correctly."""
        await broker.place_order(_make_intent(quantity=10))
        await broker.simulate_fills(
            _make_market_data(open_price=2800.0), date(2026, 1, 5)
        )

        positions = await broker.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "RELIANCE"
        assert positions[0].quantity == 10

    @pytest.mark.asyncio
    async def test_sell_fill_reduces_position(self, broker: PaperBroker) -> None:
        """SELL fill reduces/closes position correctly."""
        # First buy
        await broker.place_order(_make_intent(side=OrderSide.BUY, quantity=10))
        await broker.simulate_fills(
            _make_market_data(open_price=2800.0), date(2026, 1, 5)
        )

        # Then sell
        await broker.place_order(
            _make_intent(side=OrderSide.SELL, quantity=10)
        )
        await broker.simulate_fills(
            _make_market_data(open_price=2850.0, target_date=date(2026, 1, 6)),
            date(2026, 1, 6),
        )

        positions = await broker.get_positions()
        assert len(positions) == 0

    @pytest.mark.asyncio
    async def test_cancel_order(self, broker: PaperBroker) -> None:
        """Cancel order works from SUBMITTED state."""
        record = await broker.place_order(_make_intent())
        cancelled = await broker.cancel_order(
            record.order_id, "changed_mind"
        )
        assert cancelled.current_status == OrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_get_positions_returns_current_state(
        self, broker: PaperBroker
    ) -> None:
        """get_positions returns current state."""
        assert len(await broker.get_positions()) == 0

        await broker.place_order(_make_intent())
        await broker.simulate_fills(
            _make_market_data(open_price=2800.0), date(2026, 1, 5)
        )

        positions = await broker.get_positions()
        assert len(positions) == 1

    @pytest.mark.asyncio
    async def test_get_orders_with_status_filter(
        self, broker: PaperBroker
    ) -> None:
        """get_orders with status filter works."""
        await broker.place_order(_make_intent())
        await broker.place_order(_make_intent(symbol="TCS"))

        submitted = await broker.get_orders(OrderStatus.SUBMITTED)
        assert len(submitted) == 2

        filled = await broker.get_orders(OrderStatus.FILLED)
        assert len(filled) == 0

    @pytest.mark.asyncio
    async def test_state_persists_on_restart(self, tmp_path: Path) -> None:
        """State persists to JSON and loads correctly on restart."""
        data_dir = tmp_path / "persist_test"
        config = PaperBrokerConfig(data_dir=data_dir)

        # Create broker, place order, fill it
        broker1 = PaperBroker(config)
        broker1.set_cash(Decimal("10000000"))
        await broker1.place_order(_make_intent())
        await broker1.simulate_fills(
            _make_market_data(open_price=2800.0), date(2026, 1, 5)
        )

        positions1 = await broker1.get_positions()
        orders1 = await broker1.get_orders()
        cash1 = broker1.cash

        # Create new broker instance from same data dir
        broker2 = PaperBroker(config)
        positions2 = await broker2.get_positions()
        orders2 = await broker2.get_orders()
        cash2 = broker2.cash

        assert len(positions2) == len(positions1)
        assert positions2[0].symbol == positions1[0].symbol
        assert positions2[0].quantity == positions1[0].quantity
        assert len(orders2) == len(orders1)
        assert cash2 == cash1

    @pytest.mark.asyncio
    async def test_sell_slippage_applied_correctly(
        self, broker: PaperBroker
    ) -> None:
        """SELL slippage is applied in the opposite direction (lower fill)."""
        # Setup position first
        await broker.place_order(_make_intent(side=OrderSide.BUY, quantity=10))
        await broker.simulate_fills(
            _make_market_data(open_price=2800.0), date(2026, 1, 5)
        )

        # Place sell
        await broker.place_order(_make_intent(side=OrderSide.SELL, quantity=10))
        await broker.simulate_fills(
            _make_market_data(open_price=2900.0, target_date=date(2026, 1, 6)),
            date(2026, 1, 6),
        )

        filled = await broker.get_orders(OrderStatus.FILLED)
        sell_order = next(o for o in filled if o.intent.side == OrderSide.SELL)
        # SELL slippage: 2900 * (1 - 5/10000) = 2900 * 0.9995 = 2898.55
        expected = Decimal("2900") * (1 - Decimal("5") / Decimal("10000"))
        assert sell_order.fill_price == expected.quantize(Decimal("0.01"))
