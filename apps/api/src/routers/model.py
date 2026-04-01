"""Model router — LLM health, telemetry, and blocker scan endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from packages.contracts.llm import ModelTelemetrySummary

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/model", tags=["model"])


class BlockerScanRequest(BaseModel):
    """Request body for a blocker scan."""

    symbol: str
    headlines: list[str]
    price: float
    atr: float


@router.get("/health", response_model=APIResponse[dict[str, Any]])
async def get_model_health(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[dict[str, Any]]:
    """Return health check results for all configured providers."""
    results = await state.model_router.health_check_all()
    # Serialize ProviderHealth to dicts for JSON response
    data = {
        name: health.model_dump(mode="json") for name, health in results.items()
    }
    return APIResponse[dict[str, Any]](success=True, data=data)


@router.get("/telemetry", response_model=APIResponse[ModelTelemetrySummary])
async def get_model_telemetry(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[ModelTelemetrySummary]:
    """Return per-role, per-provider call statistics."""
    summary = state.model_telemetry.get_summary()
    return APIResponse[ModelTelemetrySummary](success=True, data=summary)


@router.post("/blocker-scan", response_model=APIResponse[dict[str, Any]])
async def run_blocker_scan(
    request: BlockerScanRequest,
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[dict[str, Any]]:
    """Run a live blocker scan via LLMBlockerProvider.

    Operator-triggered only — not called automatically by EOD flow in paper mode.
    """
    report = await state.blocker_provider.get_blocker_report(
        symbol=request.symbol,
        headlines=request.headlines,
        price=request.price,
        atr=request.atr,
    )
    return APIResponse[dict[str, Any]](
        success=True, data=report.model_dump(mode="json")
    )
