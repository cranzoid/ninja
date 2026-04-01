"""Configuration router — runtime config and history."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from packages.contracts.config_snapshot import ConfigSnapshot, RiskLimits

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse, PaginatedResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigChange(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    field: str
    old_value: str
    new_value: str


class ConfigDiff(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    snapshot_a_id: str
    snapshot_b_id: str
    snapshot_a_time: str
    snapshot_b_time: str
    changes: list[ConfigChange]


@router.get("/current", response_model=APIResponse[ConfigSnapshot])
async def get_current_config(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[ConfigSnapshot]:
    """Return the current runtime configuration snapshot."""
    return APIResponse[ConfigSnapshot](success=True, data=state.config)


@router.get("/risk-limits", response_model=APIResponse[RiskLimits])
async def get_risk_limits(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[RiskLimits]:
    """Return the current risk limits."""
    return APIResponse[RiskLimits](success=True, data=state.config.risk_limits)


@router.get("/history", response_model=PaginatedResponse[ConfigSnapshot])
async def get_config_history(
    state: Annotated[AppState, Depends(get_app_state)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[ConfigSnapshot]:
    """Return historical config snapshots captured after each EOD run."""
    snapshots = list(reversed(state.config_history))
    total = len(snapshots)
    start = (page - 1) * page_size
    return PaginatedResponse[ConfigSnapshot](
        success=True,
        data=snapshots[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/diff", response_model=APIResponse[ConfigDiff])
async def get_config_diff(
    state: Annotated[AppState, Depends(get_app_state)],
    snapshot_id_a: Annotated[str, Query()],
    snapshot_id_b: Annotated[str, Query()],
) -> APIResponse[ConfigDiff]:
    """Return a diff of two config snapshots."""
    snap_a = next(
        (s for s in state.config_history if s.snapshot_id == snapshot_id_a), None
    )
    snap_b = next(
        (s for s in state.config_history if s.snapshot_id == snapshot_id_b), None
    )

    changes: list[ConfigChange] = []

    if snap_a and snap_b:
        a_limits = snap_a.risk_limits.model_dump()
        b_limits = snap_b.risk_limits.model_dump()
        for field, a_val in a_limits.items():
            b_val = b_limits.get(field)
            if str(a_val) != str(b_val):
                changes.append(
                    ConfigChange(
                        field=f"risk_limits.{field}",
                        old_value=str(a_val),
                        new_value=str(b_val),
                    )
                )
        for field in ["mode", "armed_live", "regime_state"]:
            a_val = getattr(snap_a, field, None)
            b_val = getattr(snap_b, field, None)
            if str(a_val) != str(b_val):
                changes.append(
                    ConfigChange(
                        field=field,
                        old_value=str(a_val),
                        new_value=str(b_val),
                    )
                )

    diff = ConfigDiff(
        snapshot_a_id=snapshot_id_a,
        snapshot_b_id=snapshot_id_b,
        snapshot_a_time=snap_a.captured_at.isoformat() if snap_a else "not_found",
        snapshot_b_time=snap_b.captured_at.isoformat() if snap_b else "not_found",
        changes=changes,
    )
    return APIResponse[ConfigDiff](success=True, data=diff)
