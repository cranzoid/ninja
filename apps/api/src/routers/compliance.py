"""Compliance center router — pre-live gate status checks.

Phase 6: Now uses the real ComplianceGate instead of inline checks.
Phase 7: Added live_ready field to status endpoint.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from packages.contracts.compliance import ComplianceReport

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


class ComplianceStatusResponse(BaseModel):
    """Extended compliance response with live_ready field."""

    report: ComplianceReport
    live_ready: bool


@router.get("/status", response_model=APIResponse[ComplianceStatusResponse])
async def get_compliance_status(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[ComplianceStatusResponse]:
    """Return compliance gate status with live_ready indicator."""
    try:
        report = await state.run_compliance()
        live_ready = await state.get_live_ready()
        response = ComplianceStatusResponse(
            report=report,
            live_ready=live_ready,
        )
        return APIResponse[ComplianceStatusResponse](success=True, data=response)
    except Exception as e:
        return APIResponse[ComplianceStatusResponse](
            success=False, error=f"Compliance check failed: {e}"
        )


@router.post("/run", response_model=APIResponse[ComplianceReport])
async def run_compliance(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[ComplianceReport]:
    """Trigger a fresh compliance run and return the report."""
    try:
        report = await state.run_compliance()
        return APIResponse[ComplianceReport](success=True, data=report)
    except Exception as e:
        return APIResponse[ComplianceReport](
            success=False, error=f"Compliance check failed: {e}"
        )
