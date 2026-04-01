"""Trades and audit ledger router."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from packages.contracts.audit_event import AuditEvent
from packages.contracts.enums import OrderStatus
from packages.contracts.order_state import OrderRecord

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse, PaginatedResponse
from ..services.app_state import AppState

router = APIRouter(tags=["trades"])


def _parse_date(d: date | None) -> datetime | None:
    if d is None:
        return None
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


# --- Orders ---


@router.get("/api/trades", response_model=PaginatedResponse[OrderRecord])
async def list_trades(
    state: Annotated[AppState, Depends(get_app_state)],
    status: Annotated[Literal["filled", "cancelled", "all"] | None, Query()] = None,
    symbol: Annotated[str | None, Query()] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[OrderRecord]:
    """Return order records with optional filters."""
    status_filter: OrderStatus | None = None
    if status == "filled":
        status_filter = OrderStatus.FILLED
    elif status == "cancelled":
        status_filter = OrderStatus.CANCELLED

    orders = await state.paper_broker.get_orders(status_filter=status_filter)

    if symbol:
        orders = [o for o in orders if o.intent.symbol == symbol]

    if start_date:
        orders = [
            o for o in orders if o.created_at.date() >= start_date
        ]
    if end_date:
        orders = [o for o in orders if o.created_at.date() <= end_date]

    total = len(orders)
    start = (page - 1) * page_size
    return PaginatedResponse[OrderRecord](
        success=True,
        data=orders[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/api/trades/{order_id}", response_model=APIResponse[OrderRecord])
async def get_trade(
    order_id: str,
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[OrderRecord]:
    """Return a single order with full state transition history."""
    orders = await state.paper_broker.get_orders()
    order = next((o for o in orders if o.order_id == order_id), None)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return APIResponse[OrderRecord](success=True, data=order)


# --- Audit ledger ---


@router.get("/api/audit", response_model=PaginatedResponse[AuditEvent])
async def list_audit_events(
    state: Annotated[AppState, Depends(get_app_state)],
    event_type: Annotated[str | None, Query()] = None,
    symbol: Annotated[str | None, Query()] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[AuditEvent]:
    """Query the audit ledger with optional filters."""
    event_types = [event_type] if event_type else None
    limit = page * page_size + page_size  # over-fetch for pagination

    events = await state.audit_ledger.query(
        event_types=event_types,
        symbol=symbol,
        start_time=_parse_date(start_date),
        end_time=_parse_date(end_date),
        limit=limit,
    )

    total = len(events)
    start = (page - 1) * page_size
    return PaginatedResponse[AuditEvent](
        success=True,
        data=events[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/api/audit/{event_id}", response_model=APIResponse[AuditEvent])
async def get_audit_event(
    event_id: str,
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[AuditEvent]:
    """Return a single audit event by ID."""
    events = await state.audit_ledger.query(limit=10000)
    event = next((e for e in events if e.event_id == event_id), None)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Audit event {event_id} not found")
    return APIResponse[AuditEvent](success=True, data=event)
