"""Bot runs router — EOD run report history."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from packages.contracts.eod_report import EODRunReport

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse, PaginatedResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/runs", tags=["bot_runs"])


@router.get("", response_model=PaginatedResponse[EODRunReport])
async def list_runs(
    state: Annotated[AppState, Depends(get_app_state)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[EODRunReport]:
    """Return all EOD run reports, most recent first."""
    runs = list(reversed(state.eod_run_history))
    total = len(runs)
    start = (page - 1) * page_size
    return PaginatedResponse[EODRunReport](
        success=True,
        data=runs[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/latest", response_model=APIResponse[EODRunReport])
async def get_latest_run(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[EODRunReport]:
    """Return the most recent EOD run report."""
    report = state.get_latest_eod_report()
    if report is None:
        raise HTTPException(status_code=404, detail="No EOD runs have been completed.")
    return APIResponse[EODRunReport](success=True, data=report)


@router.get("/{run_id}", response_model=APIResponse[EODRunReport])
async def get_run(
    run_id: str,
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[EODRunReport]:
    """Return a specific EOD run report by run_id."""
    report = next(
        (r for r in state.eod_run_history if r.run_id == run_id), None
    )
    if report is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return APIResponse[EODRunReport](success=True, data=report)
