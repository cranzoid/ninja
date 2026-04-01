"""Shadow-live router — endpoints for shadow EOD runs.

Phase 6: Shadow live mode. No orders are ever placed.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from packages.contracts.broker import ShadowRunReport
from packages.contracts.enums import Mode

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse, PaginatedResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/shadow", tags=["shadow"])


class ShadowRunRequest(BaseModel):
    trading_date: str  # YYYY-MM-DD


@router.post("/run-eod", response_model=APIResponse[ShadowRunReport])
async def run_shadow_eod(
    request: ShadowRunRequest,
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[ShadowRunReport]:
    """Trigger a shadow EOD run for a given trading date.

    Validates MODE is shadow-live or returns error.
    """
    if state.config.mode not in (Mode.SHADOW_LIVE, Mode.PAPER):
        return APIResponse[ShadowRunReport](
            success=False,
            error=(
                f"Shadow EOD only available in shadow-live "
                f"or paper mode (current: {state.config.mode.value})"
            ),
        )

    try:
        trading_date = date.fromisoformat(request.trading_date)
    except ValueError:
        return APIResponse[ShadowRunReport](
            success=False,
            error=f"Invalid date format: {request.trading_date}. Use YYYY-MM-DD.",
        )

    try:
        report = await state.run_shadow_eod_and_track(trading_date)
        return APIResponse[ShadowRunReport](success=True, data=report)
    except Exception as e:
        return APIResponse[ShadowRunReport](
            success=False, error=f"Shadow EOD run failed: {e}"
        )


@router.get("/runs", response_model=PaginatedResponse[ShadowRunReport])
async def list_shadow_runs(
    state: Annotated[AppState, Depends(get_app_state)],
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[ShadowRunReport]:
    """List past shadow run reports, newest first."""
    runs = list(reversed(state.shadow_run_history))
    total = len(runs)
    start = (page - 1) * page_size
    end = start + page_size
    page_data = runs[start:end]

    return PaginatedResponse[ShadowRunReport](
        success=True,
        data=page_data,
        total=total,
        page=page,
        page_size=page_size,
    )
