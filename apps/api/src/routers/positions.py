"""Positions router — current holdings with enriched detail."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from packages.contracts.enums import PortfolioLayer

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse, PaginatedResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/positions", tags=["positions"])


class PositionDetail(BaseModel):
    """Enriched position for API display."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    symbol: str
    layer: PortfolioLayer
    quantity: int
    entry_price: Decimal
    current_price: Decimal
    stop_price: Decimal
    risk_amount: Decimal
    sector: str
    entry_date: date

    # Enriched fields
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal
    risk_pct_of_equity: Decimal
    days_held: int
    distance_to_stop_pct: Decimal
    distance_to_2r_pct: Decimal | None


def _enrich_position(
    symbol: str,
    layer: PortfolioLayer,
    quantity: int,
    entry_price: Decimal,
    current_price: Decimal,
    stop_price: Decimal,
    risk_amount: Decimal,
    sector: str,
    entry_date: date,
    equity: Decimal,
    effective_stop: Decimal,
) -> PositionDetail:
    cost_basis = entry_price * quantity
    unrealized = (current_price - entry_price) * quantity
    unrealized_pct = (
        (unrealized / cost_basis * 100).quantize(Decimal("0.01"))
        if cost_basis > 0
        else Decimal("0")
    )
    risk_pct = (
        (risk_amount / equity * 100).quantize(Decimal("0.01"))
        if equity > 0
        else Decimal("0")
    )
    days_held = (datetime.now(UTC).date() - entry_date).days
    dist_stop = (
        ((current_price - effective_stop) / current_price * 100).quantize(
            Decimal("0.01")
        )
        if current_price > 0
        else Decimal("0")
    )

    dist_2r: Decimal | None = None
    if layer == PortfolioLayer.SWING:
        risk_per_share = entry_price - stop_price
        target_2r = entry_price + 2 * risk_per_share
        if current_price > 0:
            dist_2r = (
                (target_2r - current_price) / current_price * 100
            ).quantize(Decimal("0.01"))

    return PositionDetail(
        symbol=symbol,
        layer=layer,
        quantity=quantity,
        entry_price=entry_price,
        current_price=current_price,
        stop_price=effective_stop,
        risk_amount=risk_amount,
        sector=sector,
        entry_date=entry_date,
        unrealized_pnl=unrealized,
        unrealized_pnl_pct=unrealized_pct,
        risk_pct_of_equity=risk_pct,
        days_held=days_held,
        distance_to_stop_pct=dist_stop,
        distance_to_2r_pct=dist_2r,
    )


@router.get("", response_model=PaginatedResponse[PositionDetail])
async def list_positions(
    state: Annotated[AppState, Depends(get_app_state)],
    layer: Annotated[PortfolioLayer | None, Query()] = None,
    sort_by: Annotated[
        Literal["symbol", "pnl", "risk"], Query()
    ] = "symbol",
    sort_order: Annotated[Literal["asc", "desc"], Query()] = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[PositionDetail]:
    """Return all positions with enriched display fields."""
    positions = await state.paper_broker.get_positions()
    equity = await state.get_portfolio_equity()

    if layer is not None:
        positions = [p for p in positions if p.layer == layer]

    details = [
        _enrich_position(
            symbol=p.symbol,
            layer=p.layer,
            quantity=p.quantity,
            entry_price=p.entry_price,
            current_price=p.current_price,
            stop_price=p.stop_price,
            risk_amount=p.risk_amount,
            sector=p.sector,
            entry_date=p.entry_date,
            equity=equity,
            effective_stop=state.stop_overrides.get(p.symbol, p.stop_price),
        )
        for p in positions
    ]

    if sort_by == "pnl":
        details.sort(
            key=lambda d: d.unrealized_pnl,
            reverse=(sort_order == "desc"),
        )
    elif sort_by == "risk":
        details.sort(
            key=lambda d: d.risk_pct_of_equity,
            reverse=(sort_order == "desc"),
        )
    else:
        details.sort(
            key=lambda d: d.symbol,
            reverse=(sort_order == "desc"),
        )

    total = len(details)
    start = (page - 1) * page_size
    page_data = details[start : start + page_size]

    return PaginatedResponse[PositionDetail](
        success=True,
        data=page_data,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{symbol}", response_model=APIResponse[PositionDetail])
async def get_position(
    symbol: str,
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[PositionDetail]:
    """Return enriched detail for a single position."""
    positions = await state.paper_broker.get_positions()
    equity = await state.get_portfolio_equity()

    pos = next((p for p in positions if p.symbol == symbol), None)
    if pos is None:
        raise HTTPException(status_code=404, detail=f"No open position for {symbol}")

    detail = _enrich_position(
        symbol=pos.symbol,
        layer=pos.layer,
        quantity=pos.quantity,
        entry_price=pos.entry_price,
        current_price=pos.current_price,
        stop_price=pos.stop_price,
        risk_amount=pos.risk_amount,
        sector=pos.sector,
        entry_date=pos.entry_date,
        equity=equity,
        effective_stop=state.stop_overrides.get(pos.symbol, pos.stop_price),
    )
    return APIResponse[PositionDetail](success=True, data=detail)
