"""Simulation router — run and inspect paper simulations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from packages.contracts.simulation import SimulationSummary

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse, PaginatedResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/simulation", tags=["simulation"])

_WARNING_THRESHOLD_DAYS = 50


class RunSimulationRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    start_date: date
    end_date: date
    initial_equity: Decimal = Decimal("500000")


@router.post("/run", response_model=APIResponse[SimulationSummary])
async def run_simulation(
    request: RunSimulationRequest,
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[SimulationSummary]:
    """
    Run a paper trading simulation over a date range.

    Runs synchronously. For ranges > 50 trading days, expect slow response.
    """
    from services.paper_broker.simulation_runner import _get_trading_days

    trading_days = _get_trading_days(request.start_date, request.end_date)
    if len(trading_days) > _WARNING_THRESHOLD_DAYS:
        pass  # Warning surfaced in the summary errors if needed

    summary = await state.run_tracked_simulation(
        start_date=request.start_date,
        end_date=request.end_date,
        initial_equity=request.initial_equity,
    )
    return APIResponse[SimulationSummary](success=True, data=summary)


@router.get("/history", response_model=PaginatedResponse[SimulationSummary])
async def list_simulations(
    state: Annotated[AppState, Depends(get_app_state)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[SimulationSummary]:
    """Return a paginated list of past simulations, most recent first."""
    sims = list(reversed(state.simulation_history))
    total = len(sims)
    start = (page - 1) * page_size
    return PaginatedResponse[SimulationSummary](
        success=True,
        data=sims[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{simulation_id}", response_model=APIResponse[SimulationSummary])
async def get_simulation(
    simulation_id: str,
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[SimulationSummary]:
    """Return a specific simulation by ID."""
    sim = next(
        (s for s in state.simulation_history if s.simulation_id == simulation_id),
        None,
    )
    if sim is None:
        raise HTTPException(
            status_code=404, detail=f"Simulation {simulation_id} not found."
        )
    return APIResponse[SimulationSummary](success=True, data=sim)
