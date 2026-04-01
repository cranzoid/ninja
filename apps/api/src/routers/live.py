"""Live trading router — endpoints for live EOD runs and operator review.

Phase 7: Tiny Live. Validates MODE=live, ARMED_LIVE=true, and compliance
gate all-green before proceeding with any live operation.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from packages.contracts.broker import LiveRunReport
from packages.contracts.enums import Mode

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse, PaginatedResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/live", tags=["live"])


class LiveRunRequest(BaseModel):
    trading_date: str  # YYYY-MM-DD


class ReviewRequest(BaseModel):
    notes: str


@router.post("/run-eod", response_model=APIResponse[LiveRunReport])
async def run_live_eod(
    request: LiveRunRequest,
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[LiveRunReport]:
    """Trigger a live EOD run for a given trading date.

    Validates MODE=live, ARMED_LIVE=true, and compliance gate all-green.
    """
    # Validate mode
    if state.config.mode != Mode.LIVE:
        return APIResponse[LiveRunReport](
            success=False,
            error=f"Live EOD requires MODE=live (current: {state.config.mode.value})",
        )

    if not state.config.armed_live:
        return APIResponse[LiveRunReport](
            success=False,
            error="Live EOD requires ARMED_LIVE=true",
        )

    # Run compliance check
    try:
        compliance = await state.run_compliance()
        if not compliance.all_blocking_passed:
            failed = [
                r.check_name
                for r in compliance.results
                if r.status.value == "fail"
            ]
            return APIResponse[LiveRunReport](
                success=False,
                error=f"Compliance checks not all-green: {', '.join(failed)}",
            )
    except Exception as e:
        return APIResponse[LiveRunReport](
            success=False,
            error=f"Compliance check failed: {e}",
        )

    # Check for unresolved anomalies from previous run
    if state.live_run_history:
        last = state.live_run_history[-1]
        gate = state.review_gate
        if gate and gate.has_unresolved_anomalies(last):
            return APIResponse[LiveRunReport](
                success=False,
                error=(
                    "Previous live session has unresolved "
                    "anomalies. Review required."
                ),
            )

    # Parse date
    try:
        trading_date = date.fromisoformat(request.trading_date)
    except ValueError:
        return APIResponse[LiveRunReport](
            success=False,
            error=f"Invalid date format: {request.trading_date}. Use YYYY-MM-DD.",
        )

    # Execute
    try:
        report = await state.run_live_eod_and_track(trading_date)
        return APIResponse[LiveRunReport](success=True, data=report)
    except Exception as e:
        return APIResponse[LiveRunReport](
            success=False, error=f"Live EOD run failed: {e}"
        )


@router.get("/runs", response_model=PaginatedResponse[LiveRunReport])
async def list_live_runs(
    state: Annotated[AppState, Depends(get_app_state)],
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[LiveRunReport]:
    """List past live run reports, newest first."""
    runs = list(reversed(state.live_run_history))
    total = len(runs)
    start = (page - 1) * page_size
    end = start + page_size
    page_data = runs[start:end]

    return PaginatedResponse[LiveRunReport](
        success=True,
        data=page_data,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/runs/{trading_date}/review",
    response_model=APIResponse[LiveRunReport],
)
async def review_live_run(
    trading_date: str,
    request: ReviewRequest,
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[LiveRunReport]:
    """Mark a live run as operator-reviewed. Requires non-empty notes."""
    if not request.notes.strip():
        return APIResponse[LiveRunReport](
            success=False,
            error="Review notes must not be empty.",
        )

    try:
        target_date = date.fromisoformat(trading_date)
    except ValueError:
        return APIResponse[LiveRunReport](
            success=False,
            error=f"Invalid date format: {trading_date}. Use YYYY-MM-DD.",
        )

    # Find the report for this date
    report = next(
        (r for r in state.live_run_history if r.trading_date == target_date),
        None,
    )
    if report is None:
        return APIResponse[LiveRunReport](
            success=False,
            error=f"No live run report found for {trading_date}.",
        )

    # Mark reviewed
    if state.review_gate:
        report = state.review_gate.mark_reviewed(report, request.notes)
        await state.review_gate.log_review(report, request.notes)

    return APIResponse[LiveRunReport](success=True, data=report)


@router.get(
    "/runs/{trading_date}/can-proceed",
    response_model=APIResponse[bool],
)
async def can_proceed(
    trading_date: str,
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[bool]:
    """Check if the next session can run (no unresolved anomalies)."""
    if not state.live_run_history:
        return APIResponse[bool](success=True, data=True)

    last_report = state.live_run_history[-1]
    if state.review_gate:
        can_run = state.review_gate.can_run_next_session(last_report)
    else:
        can_run = True

    return APIResponse[bool](success=True, data=can_run)
