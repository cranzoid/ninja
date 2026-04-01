"""Paper broker — simulates broker execution for paper trading.

Fills at next-open with configurable slippage. Maintains its own order book
and position state. Implements the same interface that the live broker will use.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd

from packages.contracts.audit_event import AuditEvent
from packages.contracts.broker_config import PaperBrokerConfig, Quote
from packages.contracts.enums import OrderSide, OrderStatus, PortfolioLayer
from packages.contracts.order_intent import OrderIntent
from packages.contracts.order_state import OrderRecord
from packages.contracts.portfolio import Position

from .state_machine import OrderStateMachine

logger = logging.getLogger(__name__)


class PaperBroker:
    """
    Simulates broker execution for paper trading.
    Fills at next-open with configurable slippage.
    Maintains its own order book and position state.
    """

    def __init__(self, config: PaperBrokerConfig) -> None:
        self._config = config
        self._data_dir = config.data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # Internal state
        self._machines: dict[str, OrderStateMachine] = {}
        self._orders: dict[str, OrderRecord] = {}
        self._positions: dict[str, _PositionState] = {}
        self._cash: Decimal = Decimal("0")

        # Load persisted state
        self._load_state()

    # --- Broker adapter interface (charter section 11) ---

    async def authenticate(self) -> bool:
        """Always returns True for paper mode."""
        return True

    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Not implemented for paper mode — use market data directly."""
        return {}

    async def place_order(self, intent: OrderIntent) -> OrderRecord:
        """Accept an OrderIntent, create an order, and submit it."""
        machine = OrderStateMachine(intent)
        # Immediately submit
        machine.submit()

        self._machines[machine.record.order_id] = machine
        self._orders[machine.record.order_id] = machine.record
        self._save_state()

        return machine.record

    async def modify_order(
        self, order_id: str, modifications: dict[str, object]
    ) -> OrderRecord:
        """Modify an existing order. Limited support in paper mode."""
        if order_id not in self._orders:
            raise ValueError(f"Order {order_id} not found")
        return self._orders[order_id]

    async def cancel_order(self, order_id: str, reason: str) -> OrderRecord:
        """Cancel an order."""
        if order_id not in self._machines:
            raise ValueError(f"Order {order_id} not found")

        machine = self._machines[order_id]
        machine.cancel(reason)
        self._orders[order_id] = machine.record
        self._save_state()

        return machine.record

    async def get_positions(self) -> list[Position]:
        """Return current positions as contract Position objects."""
        result: list[Position] = []
        for ps in self._positions.values():
            if ps.quantity > 0:
                result.append(ps.to_position())
        return result

    async def get_orders(
        self, status_filter: OrderStatus | None = None
    ) -> list[OrderRecord]:
        """Return orders, optionally filtered by status."""
        if status_filter is None:
            return list(self._orders.values())
        return [
            o for o in self._orders.values() if o.current_status == status_filter
        ]

    async def healthcheck(self) -> bool:
        """Always healthy for paper mode."""
        return True

    # --- Paper-specific ---

    async def simulate_fills(
        self,
        market_data: dict[str, pd.DataFrame],
        current_date: date,
    ) -> list[AuditEvent]:
        """
        Simulate fills for all SUBMITTED orders using the current day's open.

        Called once per simulated trading day. For each SUBMITTED order:
        1. Look up the current day's open price for that symbol
        2. Apply slippage
        3. Transition order to FILLED via state machine
        4. Update internal position tracking
        """
        events: list[AuditEvent] = []

        submitted_orders = [
            (oid, m)
            for oid, m in self._machines.items()
            if m.current_status == OrderStatus.SUBMITTED
        ]

        for order_id, machine in submitted_orders:
            record = machine.record
            symbol = record.intent.symbol
            df = market_data.get(symbol)

            if df is None or df.empty:
                logger.warning(
                    "No market data for %s on %s, skipping fill", symbol, current_date
                )
                continue

            # Find today's row
            day_row = None
            for _, row in df.iterrows():
                row_date = row["date"]
                if isinstance(row_date, datetime):
                    row_date = row_date.date()
                if row_date == current_date:
                    day_row = row
                    break

            if day_row is None:
                continue

            open_price = Decimal(str(round(float(day_row["open"]), 2)))

            # Apply slippage
            slippage_mult = Decimal(str(self._config.slippage_bps)) / Decimal("10000")
            if record.intent.side == OrderSide.BUY:
                fill_price = open_price * (1 + slippage_mult)
            else:
                fill_price = open_price * (1 - slippage_mult)
            fill_price = fill_price.quantize(Decimal("0.01"))

            fill_qty = record.remaining_qty
            now = datetime.now(UTC)

            # Transition to FILLED
            event = machine.fill(fill_price, fill_qty, now)
            events.append(event)

            # Update position tracking
            self._update_position_on_fill(record.intent, fill_price, fill_qty)

            # Update order record
            self._orders[order_id] = machine.record

        if events:
            self._save_state()

        return events

    def set_cash(self, amount: Decimal) -> None:
        """Set the cash balance (used during initialization)."""
        self._cash = amount
        self._save_state()

    @property
    def cash(self) -> Decimal:
        return self._cash

    # --- Position tracking ---

    def _update_position_on_fill(
        self,
        intent: OrderIntent,
        fill_price: Decimal,
        fill_qty: int,
    ) -> None:
        """Update position state after a fill."""
        symbol = intent.symbol

        if intent.side == OrderSide.BUY:
            cost = fill_price * fill_qty
            self._cash -= cost

            if symbol in self._positions:
                ps = self._positions[symbol]
                # Average entry price for multi-lot
                total_cost = ps.avg_entry_price * ps.quantity + fill_price * fill_qty
                new_qty = ps.quantity + fill_qty
                ps.avg_entry_price = (total_cost / new_qty).quantize(Decimal("0.01"))
                ps.quantity = new_qty
                ps.current_price = fill_price
            else:
                self._positions[symbol] = _PositionState(
                    symbol=symbol,
                    layer=intent.layer,
                    quantity=fill_qty,
                    avg_entry_price=fill_price,
                    current_price=fill_price,
                    stop_price=intent.stop_price,
                    risk_amount=intent.risk_amount,
                    sector=_symbol_to_sector(symbol),
                    entry_date=datetime.now(UTC).date(),
                )
        else:
            # SELL
            proceeds = fill_price * fill_qty
            self._cash += proceeds

            if symbol in self._positions:
                ps = self._positions[symbol]
                ps.quantity -= fill_qty
                if ps.quantity <= 0:
                    del self._positions[symbol]

    def update_current_prices(
        self, market_data: dict[str, pd.DataFrame], target_date: date
    ) -> None:
        """Update current prices on all positions from market data."""
        for symbol, ps in self._positions.items():
            df = market_data.get(symbol)
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                row_date = row["date"]
                if isinstance(row_date, datetime):
                    row_date = row_date.date()
                if row_date == target_date:
                    ps.current_price = Decimal(
                        str(round(float(row["close"]), 2))
                    )
                    break

    # --- Persistence ---

    def _save_state(self) -> None:
        """Persist all state to JSON files."""
        # Orders — serialize each record individually to preserve types on reload
        orders_json_lines = []
        for record in self._orders.values():
            orders_json_lines.append(record.model_dump_json())
        orders_path = self._data_dir / "orders.jsonl"
        orders_path.write_text("\n".join(orders_json_lines))

        # Positions
        positions_data = {}
        for sym, ps in self._positions.items():
            positions_data[sym] = ps.to_dict()
        positions_path = self._data_dir / "positions.json"
        positions_path.write_text(json.dumps(positions_data, default=str, indent=2))

        # Cash
        cash_path = self._data_dir / "cash.json"
        cash_path.write_text(json.dumps({"cash": str(self._cash)}))

    def _load_state(self) -> None:
        """Load persisted state from JSON files."""
        # Cash
        cash_path = self._data_dir / "cash.json"
        if cash_path.exists():
            data = json.loads(cash_path.read_text())
            self._cash = Decimal(data["cash"])

        # Positions
        positions_path = self._data_dir / "positions.json"
        if positions_path.exists():
            data = json.loads(positions_path.read_text())
            for sym, ps_data in data.items():
                self._positions[sym] = _PositionState.from_dict(ps_data)

        # Orders — reload as OrderRecords (state machines are not reconstructed
        # for filled/terminal orders, only for active ones)
        orders_path = self._data_dir / "orders.jsonl"
        if orders_path.exists():
            for line in orders_path.read_text().splitlines():
                if not line.strip():
                    continue
                record = OrderRecord.model_validate_json(line)
                self._orders[record.order_id] = record
                # Reconstruct state machine for non-terminal orders
                if record.current_status in (
                    OrderStatus.PENDING,
                    OrderStatus.SUBMITTED,
                    OrderStatus.PARTIALLY_FILLED,
                ):
                    machine = OrderStateMachine(record.intent)
                    machine._record = record
                    machine._transitions = list(record.transitions)
                    self._machines[record.order_id] = machine


class _PositionState:
    """Mutable internal position tracking state."""

    def __init__(
        self,
        symbol: str,
        layer: PortfolioLayer,
        quantity: int,
        avg_entry_price: Decimal,
        current_price: Decimal,
        stop_price: Decimal,
        risk_amount: Decimal,
        sector: str,
        entry_date: date,
    ) -> None:
        self.symbol = symbol
        self.layer = layer
        self.quantity = quantity
        self.avg_entry_price = avg_entry_price
        self.current_price = current_price
        self.stop_price = stop_price
        self.risk_amount = risk_amount
        self.sector = sector
        self.entry_date = entry_date

    def to_position(self) -> Position:
        """Convert to immutable contract Position."""
        return Position(
            symbol=self.symbol,
            layer=self.layer,
            quantity=self.quantity,
            entry_price=self.avg_entry_price,
            current_price=self.current_price,
            stop_price=self.stop_price,
            risk_amount=self.risk_amount,
            sector=self.sector,
            entry_date=self.entry_date,
        )

    def to_dict(self) -> dict[str, str | int]:
        return {
            "symbol": self.symbol,
            "layer": self.layer.value,
            "quantity": self.quantity,
            "avg_entry_price": str(self.avg_entry_price),
            "current_price": str(self.current_price),
            "stop_price": str(self.stop_price),
            "risk_amount": str(self.risk_amount),
            "sector": self.sector,
            "entry_date": self.entry_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> _PositionState:
        return cls(
            symbol=str(data["symbol"]),
            layer=PortfolioLayer(str(data["layer"])),
            quantity=int(str(data["quantity"])),
            avg_entry_price=Decimal(str(data["avg_entry_price"])),
            current_price=Decimal(str(data["current_price"])),
            stop_price=Decimal(str(data["stop_price"])),
            risk_amount=Decimal(str(data["risk_amount"])),
            sector=str(data["sector"]),
            entry_date=date.fromisoformat(str(data["entry_date"])),
        )


# Simplified sector mapping for paper mode
_SECTOR_MAP: dict[str, str] = {
    "RELIANCE": "energy",
    "TCS": "it",
    "INFY": "it",
    "HDFCBANK": "banking",
    "ICICIBANK": "banking",
    "BHARTIARTL": "telecom",
    "ITC": "fmcg",
    "SBIN": "banking",
    "LT": "infrastructure",
    "KOTAKBANK": "banking",
    "AXISBANK": "banking",
    "HINDUNILVR": "fmcg",
    "MARUTI": "auto",
    "TATAMOTORS": "auto",
    "SUNPHARMA": "pharma",
    "WIPRO": "it",
    "TITAN": "consumer",
    "ULTRACEMCO": "cement",
    "BAJFINANCE": "nbfc",
    "NESTLEIND": "fmcg",
    "ADANIENT": "conglomerate",
    "TECHM": "it",
    "POWERGRID": "utilities",
    "NTPC": "utilities",
    "ONGC": "energy",
}


def _symbol_to_sector(symbol: str) -> str:
    return _SECTOR_MAP.get(symbol, "unknown")
