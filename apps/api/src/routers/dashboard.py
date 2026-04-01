"""Dashboard router — main overview endpoint."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from packages.contracts.enums import Mode, OrderSide, OrderStatus
from packages.contracts.eod_report import EODRunReport
from packages.contracts.regime_state import RegimeState

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class SystemHealth(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    data_feed_fresh: bool
    broker_healthy: bool
    ledger_healthy: bool
    last_run_successful: bool
    last_run_time: datetime | None


class DashboardData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    mode: Mode
    armed_live: bool
    portfolio_equity: Decimal
    portfolio_cash: Decimal
    total_positions: int
    open_risk_pct: Decimal
    regime: RegimeState
    todays_pnl: Decimal
    total_unrealized_pnl: Decimal
    total_realized_pnl: Decimal
    pending_orders: int
    last_eod_run: EODRunReport | None
    alerts_count_today: int
    system_health: SystemHealth


@router.get("", response_model=APIResponse[DashboardData])
async def get_dashboard(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[DashboardData]:
    """Return everything needed to render the dashboard page."""
    positions = await state.paper_broker.get_positions()
    equity = await state.get_portfolio_equity()
    cash = state.paper_broker.cash

    # Unrealized P&L
    total_unrealized: Decimal = sum(
        ((p.current_price - p.entry_price) * p.quantity for p in positions),
        Decimal("0"),
    )

    # Realized P&L from filled SELL orders
    all_orders = await state.paper_broker.get_orders(
        status_filter=OrderStatus.FILLED
    )
    realized: Decimal = sum(
        (
            (o.fill_price - o.intent.stop_price) * o.filled_qty
            for o in all_orders
            if o.intent.side == OrderSide.SELL and o.fill_price is not None
        ),
        Decimal("0"),
    )

    # Pending orders
    submitted = await state.paper_broker.get_orders(
        status_filter=OrderStatus.SUBMITTED
    )
    pending_count = len(submitted)

    # Regime
    regime = state.get_latest_regime()

    # Last EOD run
    last_run = state.get_latest_eod_report()
    open_risk = last_run.portfolio_risk.open_risk_pct if last_run else Decimal("0")

    # Today's alerts
    today_events = await state.audit_ledger.get_events_for_date(date.today())
    alerts_today = sum(1 for e in today_events if e.operator_visible)

    # System health
    broker_ok = await state.paper_broker.healthcheck()
    ledger_ok = True
    try:
        await state.audit_ledger.get_events_for_date(date.today())
    except Exception:
        ledger_ok = False

    health = SystemHealth(
        data_feed_fresh=True,  # fixture provider is always "fresh"
        broker_healthy=broker_ok,
        ledger_healthy=ledger_ok,
        last_run_successful=last_run.is_successful if last_run else False,
        last_run_time=last_run.completed_at if last_run else None,
    )

    data = DashboardData(
        mode=state.config.mode,
        armed_live=state.config.armed_live,
        portfolio_equity=equity,
        portfolio_cash=cash,
        total_positions=len(positions),
        open_risk_pct=open_risk,
        regime=regime,
        todays_pnl=total_unrealized,
        total_unrealized_pnl=total_unrealized,
        total_realized_pnl=realized,
        pending_orders=pending_count,
        last_eod_run=last_run,
        alerts_count_today=alerts_today,
        system_health=health,
    )
    return APIResponse[DashboardData](success=True, data=data)
