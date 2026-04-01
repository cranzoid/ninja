"""Today's plan router — pending entries, exits, watchlist."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from packages.contracts.candidates import SwingCandidate
from packages.contracts.enums import (
    BlockerCategory,
    OrderSide,
    OrderStatus,
    PortfolioLayer,
)
from packages.contracts.eod_report import EODRunReport
from packages.contracts.order_state import OrderRecord
from packages.contracts.regime_state import RegimeState

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/plan", tags=["plan"])


class ExitWatchItem(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    symbol: str
    layer: PortfolioLayer
    current_price: Decimal
    stop_price: Decimal
    distance_to_stop_pct: Decimal
    distance_to_2r_pct: Decimal | None
    days_below_200dma: int


class BlockedSymbolSummary(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    symbol: str
    blocker_categories: list[BlockerCategory]
    expires_at: date | None


class TodaysPlan(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    trading_date: date
    regime: RegimeState
    pending_entries: list[OrderRecord]
    pending_exits: list[OrderRecord]
    exit_watchlist: list[ExitWatchItem]
    candidate_preview: list[SwingCandidate]
    blocked_symbols: list[BlockedSymbolSummary]


class RunEODRequest(BaseModel):
    trading_date: date


@router.get("/today", response_model=APIResponse[TodaysPlan])
async def get_todays_plan(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[TodaysPlan]:
    """Return today's trading plan: pending orders, exit watchlist, candidates."""
    regime = state.get_latest_regime()

    # Pending entries (submitted BUY orders)
    submitted = await state.paper_broker.get_orders(status_filter=OrderStatus.SUBMITTED)
    pending_entries = [o for o in submitted if o.intent.side == OrderSide.BUY]
    pending_exits = [o for o in submitted if o.intent.side == OrderSide.SELL]

    # Exit watchlist — positions approaching exit triggers
    positions = await state.paper_broker.get_positions()
    watchlist: list[ExitWatchItem] = []

    for pos in positions:
        effective_stop = state.stop_overrides.get(pos.symbol, pos.stop_price)
        if pos.current_price > 0:
            distance_to_stop = (
                (pos.current_price - effective_stop) / pos.current_price * 100
            ).quantize(Decimal("0.01"))
        else:
            distance_to_stop = Decimal("0")

        # 2R target only for SWING
        distance_to_2r: Decimal | None = None
        if pos.layer == PortfolioLayer.SWING:
            risk_per_share = pos.entry_price - pos.stop_price
            target_2r = pos.entry_price + 2 * risk_per_share
            if pos.current_price > 0:
                distance_to_2r = (
                    (target_2r - pos.current_price) / pos.current_price * 100
                ).quantize(Decimal("0.01"))

        days_below = state.stop_manager._consecutive_days_below_200dma.get(
            pos.symbol, 0
        )

        watchlist.append(
            ExitWatchItem(
                symbol=pos.symbol,
                layer=pos.layer,
                current_price=pos.current_price,
                stop_price=effective_stop,
                distance_to_stop_pct=distance_to_stop,
                distance_to_2r_pct=distance_to_2r,
                days_below_200dma=days_below,
            )
        )

    # Candidate preview from last EOD run (if available)
    candidates: list[SwingCandidate] = []

    # Frozen / blocked symbols
    blocked: list[BlockedSymbolSummary] = [
        BlockedSymbolSummary(
            symbol=sym,
            blocker_categories=[BlockerCategory.REGIME_BLOCK],
            expires_at=None,
        )
        for sym in state.frozen_symbols
    ]

    plan = TodaysPlan(
        trading_date=date.today(),
        regime=regime,
        pending_entries=pending_entries,
        pending_exits=pending_exits,
        exit_watchlist=watchlist,
        candidate_preview=candidates,
        blocked_symbols=blocked,
    )
    return APIResponse[TodaysPlan](success=True, data=plan)


@router.post("/run-eod", response_model=APIResponse[EODRunReport])
async def run_eod(
    request: RunEODRequest,
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[EODRunReport]:
    """Manually trigger an EOD run for the given trading date."""
    report = await state.run_eod_and_track(request.trading_date)
    return APIResponse[EODRunReport](success=True, data=report)
