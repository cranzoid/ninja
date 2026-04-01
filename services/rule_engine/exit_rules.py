"""Exit rule evaluator — applies charter exit rules to open positions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd

from packages.contracts.decisions import ExitDecision
from packages.contracts.enums import (
    ExecutionTiming,
    Mode,
    OrderSide,
    OrderType,
    PortfolioLayer,
)
from packages.contracts.order_intent import OrderIntent
from packages.contracts.portfolio import Position
from packages.contracts.regime_state import RegimeState


def _make_exit_intent(
    position: Position,
    quantity: int,
    regime: RegimeState,
    mode: Mode = Mode.PAPER,
) -> OrderIntent:
    """Create an exit OrderIntent for a position."""
    qty_ratio = Decimal(str(quantity)) / Decimal(str(position.quantity))
    risk_amount = position.risk_amount * qty_ratio
    return OrderIntent(
        intent_id=str(uuid.uuid4()),
        symbol=position.symbol,
        layer=position.layer,
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=quantity,
        stop_price=position.stop_price,
        risk_amount=risk_amount,
        risk_pct_of_equity=Decimal("0.00"),
        execution_timing=ExecutionTiming.NEXT_OPEN,
        regime_at_intent=regime.regime_class,
        created_at=datetime.now(UTC),
        approved_by="rule_engine",
        mode=mode,
    )


def evaluate_exits(
    positions: list[Position],
    featured_data: dict[str, pd.DataFrame],
    regime: RegimeState,
    mode: Mode = Mode.PAPER,
) -> list[ExitDecision]:
    """
    Evaluate all open positions for exit conditions.

    Swing exits (charter §6.5):
    - Stop hit: current price <= stop → exit full
    - Partial profit at +2R: unrealized >= 2x risk_per_share → exit 50%
    - Trail stop: close < 10-DMA → exit remainder

    Core exits (charter §6.4):
    - 200-DMA break: close < 200-DMA for 3 consecutive sessions → exit full
    """
    decisions: list[ExitDecision] = []

    for pos in positions:
        df = featured_data.get(pos.symbol)
        if df is None or df.empty:
            decisions.append(ExitDecision(
                symbol=pos.symbol,
                layer=pos.layer,
                decision="hold",
                exit_reason="no_data_available",
            ))
            continue

        latest = df.iloc[-1]
        current_price = Decimal(str(round(float(latest["close"]), 2)))

        if pos.layer == PortfolioLayer.SWING:
            decision = _evaluate_swing_exit(pos, df, current_price, regime, mode)
        else:
            decision = _evaluate_core_exit(pos, df, current_price, regime, mode)

        decisions.append(decision)

    return decisions


def _evaluate_swing_exit(
    pos: Position,
    df: pd.DataFrame,
    current_price: Decimal,
    regime: RegimeState,
    mode: Mode,
) -> ExitDecision:
    """Apply swing exit rules in priority order."""
    # 1. Stop hit
    if current_price <= pos.stop_price:
        return ExitDecision(
            symbol=pos.symbol,
            layer=pos.layer,
            decision="exit_full",
            exit_reason="stop_hit",
            order_intent=_make_exit_intent(pos, pos.quantity, regime, mode),
        )

    # 2. Partial profit at +2R
    risk_per_share = pos.entry_price - pos.stop_price
    unrealized_per_share = current_price - pos.entry_price
    if risk_per_share > 0 and unrealized_per_share >= 2 * risk_per_share:
        partial_qty = max(1, pos.quantity // 2)
        return ExitDecision(
            symbol=pos.symbol,
            layer=pos.layer,
            decision="exit_partial",
            exit_reason="partial_profit_2R",
            order_intent=_make_exit_intent(pos, partial_qty, regime, mode),
        )

    # 3. Trail stop: close < 10-DMA
    latest = df.iloc[-1]
    dma_10 = latest.get("dma_10")
    if pd.notna(dma_10) and current_price < Decimal(str(round(float(dma_10), 2))):
        return ExitDecision(
            symbol=pos.symbol,
            layer=pos.layer,
            decision="exit_full",
            exit_reason="trail_stop_10dma",
            order_intent=_make_exit_intent(pos, pos.quantity, regime, mode),
        )

    return ExitDecision(
        symbol=pos.symbol,
        layer=pos.layer,
        decision="hold",
    )


def _evaluate_core_exit(
    pos: Position,
    df: pd.DataFrame,
    current_price: Decimal,
    regime: RegimeState,
    mode: Mode,
) -> ExitDecision:
    """Apply core exit rules."""
    # 200-DMA break: close < 200-DMA for 3 consecutive sessions
    if len(df) >= 3 and "dma_200" in df.columns:
        last_3 = df.tail(3)
        below_200dma = all(
            pd.notna(row.get("dma_200")) and row["close"] < row["dma_200"]
            for _, row in last_3.iterrows()
        )
        if below_200dma:
            return ExitDecision(
                symbol=pos.symbol,
                layer=pos.layer,
                decision="exit_full",
                exit_reason="200dma_break_3_sessions",
                order_intent=_make_exit_intent(pos, pos.quantity, regime, mode),
            )

    return ExitDecision(
        symbol=pos.symbol,
        layer=pos.layer,
        decision="hold",
    )
