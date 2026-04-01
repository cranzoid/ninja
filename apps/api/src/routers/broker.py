"""Broker router — health and session endpoints.

Phase 6: Broker adapter health monitoring.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from packages.contracts.broker import BrokerHealth, BrokerSession

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/broker", tags=["broker"])


@router.get("/health", response_model=APIResponse[BrokerHealth])
async def get_broker_health(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[BrokerHealth]:
    """Return broker adapter health status."""
    if state.mock_broker is None:
        return APIResponse[BrokerHealth](
            success=False, error="No broker adapter configured."
        )

    try:
        health = await state.mock_broker.healthcheck()
        return APIResponse[BrokerHealth](success=True, data=health)
    except Exception as e:
        return APIResponse[BrokerHealth](
            success=False, error=f"Broker health check failed: {e}"
        )


@router.get("/session", response_model=APIResponse[BrokerSession])
async def get_broker_session(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[BrokerSession]:
    """Return current broker session info (without credentials)."""
    if state.mock_broker is None:
        return APIResponse[BrokerSession](
            success=False, error="No broker adapter configured."
        )

    if state.mock_broker._session is None:
        return APIResponse[BrokerSession](
            success=False, error="No active broker session."
        )

    return APIResponse[BrokerSession](
        success=True, data=state.mock_broker._session
    )
