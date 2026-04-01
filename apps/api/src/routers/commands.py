"""Command center router — operator override commands.

Charter §11.4: Only risk-reducing overrides are allowed.
Every command produces an AuditEvent with event_type='override_applied'.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, field_validator

from packages.contracts.enums import OverrideAction
from packages.contracts.order_state import OrderRecord

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse, PaginatedResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/commands", tags=["commands"])


class OperatorCommand(BaseModel):
    """An operator override command. All commands must include a non-empty reason."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    command_type: OverrideAction
    symbol: str
    parameters: dict[str, object] = {}
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reason must not be empty")
        return v


class CommandResult(BaseModel):
    """Result of executing an operator command."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    command_id: str
    command_type: OverrideAction
    symbol: str
    status: Literal["executed", "rejected", "error"]
    message: str
    audit_event_id: str
    resulting_order: OrderRecord | None = None


class UnfreezeRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reason must not be empty")
        return v


@router.post("/execute", response_model=APIResponse[CommandResult])
async def execute_command(
    command: OperatorCommand,
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[CommandResult]:
    """
    Execute an operator override command.

    Only risk-reducing overrides are allowed (charter §11.4):
    CANCEL_ENTRY, REDUCE_SIZE, TIGHTEN_STOP, CLOSE_POSITION, FREEZE_SYMBOL.
    """
    import uuid

    status, message, result_order = await state.execute_command(
        command_type=command.command_type,
        symbol=command.symbol,
        parameters=command.parameters,
        reason=command.reason,
    )

    # The audit event ID is the command_id embedded in the override_applied event.
    # We look it up from recent override events for this symbol.
    events = await state.audit_ledger.query(
        event_types=["override_applied"],
        symbol=command.symbol,
        limit=1,
    )
    audit_event_id = events[-1].event_id if events else str(uuid.uuid4())

    result = CommandResult(
        command_id=audit_event_id,
        command_type=command.command_type,
        symbol=command.symbol,
        status=status,  # type: ignore[arg-type]
        message=message,
        audit_event_id=audit_event_id,
        resulting_order=result_order,
    )
    return APIResponse[CommandResult](success=True, data=result)


@router.get("/history", response_model=PaginatedResponse[object])
async def get_command_history(
    state: Annotated[AppState, Depends(get_app_state)],
    symbol: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[object]:
    """Return override command history from the audit ledger."""
    events = await state.audit_ledger.query(
        event_types=["override_applied"],
        symbol=symbol,
        limit=10000,
    )
    total = len(events)
    start = (page - 1) * page_size
    page_events = events[start : start + page_size]
    return PaginatedResponse[object](
        success=True,
        data=list(page_events),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/frozen-symbols", response_model=APIResponse[list[str]])
async def get_frozen_symbols(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[list[str]]:
    """Return currently frozen symbols."""
    return APIResponse[list[str]](
        success=True, data=sorted(state.frozen_symbols)
    )


@router.post("/unfreeze/{symbol}", response_model=APIResponse[str])
async def unfreeze_symbol(
    symbol: str,
    body: UnfreezeRequest,
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[str]:
    """Unfreeze a symbol, allowing new entries again."""
    import uuid
    from datetime import UTC, datetime

    from packages.contracts.audit_event import AuditEvent

    if symbol not in state.frozen_symbols:
        return APIResponse[str](
            success=False,
            error=f"{symbol} is not currently frozen.",
        )

    state.frozen_symbols.discard(symbol)

    event = AuditEvent(
        event_id=str(uuid.uuid4()),
        timestamp=datetime.now(UTC),
        event_type="override_applied",
        source_service="operator_console",
        mode=state.config.mode,
        payload={
            "command_type": "unfreeze_symbol",
            "symbol": symbol,
            "reason": body.reason,
        },
        related_symbol=symbol,
        operator_visible=True,
    )
    await state.audit_ledger.record(event)

    return APIResponse[str](success=True, data=f"{symbol} unfrozen.")
