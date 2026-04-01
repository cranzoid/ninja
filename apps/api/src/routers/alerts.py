"""Alerts feed router — operator-visible audit events."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from packages.contracts.audit_event import AuditEvent

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse, PaginatedResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AcknowledgeRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    acknowledged_at: datetime | None = None


@router.get("", response_model=PaginatedResponse[AuditEvent])
async def list_alerts(
    state: Annotated[AppState, Depends(get_app_state)],
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedResponse[AuditEvent]:
    """Return operator-visible audit events with optional date filters."""

    def _dt(d: date) -> datetime:
        return datetime(d.year, d.month, d.day, tzinfo=UTC)

    events = await state.audit_ledger.query(
        start_time=_dt(start_date) if start_date else None,
        end_time=_dt(end_date) if end_date else None,
        limit=10000,
    )
    alerts = [e for e in events if e.operator_visible]
    total = len(alerts)
    start = (page - 1) * page_size
    return PaginatedResponse[AuditEvent](
        success=True,
        data=alerts[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/today", response_model=APIResponse[list[AuditEvent]])
async def get_todays_alerts(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[list[AuditEvent]]:
    """Return all operator-visible alerts for today."""
    events = await state.audit_ledger.get_events_for_date(date.today())
    alerts = [e for e in events if e.operator_visible]
    return APIResponse[list[AuditEvent]](success=True, data=alerts)


@router.post("/{event_id}/acknowledge", response_model=APIResponse[str])
async def acknowledge_alert(
    event_id: str,
    state: Annotated[AppState, Depends(get_app_state)],
    body: AcknowledgeRequest | None = None,
) -> APIResponse[str]:
    """Mark an alert as acknowledged by the operator."""
    ack_time = (
        body.acknowledged_at if body and body.acknowledged_at else None
    ) or datetime.now(UTC)
    state.alert_acknowledgments[event_id] = ack_time
    return APIResponse[str](
        success=True,
        data=f"Event {event_id} acknowledged at {ack_time.isoformat()}",
    )
