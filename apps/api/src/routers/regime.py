"""Regime router — current regime state and history."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from packages.contracts.regime_state import RegimeState

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse, PaginatedResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/regime", tags=["regime"])


@router.get("/current", response_model=APIResponse[RegimeState])
async def get_current_regime(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[RegimeState]:
    """Return the latest regime assessment."""
    return APIResponse[RegimeState](
        success=True, data=state.get_latest_regime()
    )


@router.get("/history", response_model=PaginatedResponse[RegimeState])
async def get_regime_history(
    state: Annotated[AppState, Depends(get_app_state)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> PaginatedResponse[RegimeState]:
    """Return regime history from EOD run reports."""
    regimes = [r.regime for r in state.eod_run_history]
    regimes = list(reversed(regimes[-days:]))
    total = len(regimes)
    start = (page - 1) * page_size
    return PaginatedResponse[RegimeState](
        success=True,
        data=regimes[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )
