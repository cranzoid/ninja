"""Broker adapter contracts — protocol, session, health, and shadow-run schemas.

Phase 6: Shadow Live. These contracts define the interface that all broker
adapters (paper, mock, Zerodha, etc.) must implement. The BrokerAdapter
protocol is the single source of truth for broker interactions.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator

from .blocker_report import BlockerReport
from .broker_config import Quote
from .order_intent import OrderIntent
from .order_state import OrderRecord
from .portfolio import Position
from .reconciliation import ReconciliationReport
from .risk import PortfolioRisk


class BrokerSession(BaseModel):
    """Active broker session information."""

    model_config = ConfigDict(strict=True, frozen=True)

    session_id: str
    expires_at: datetime
    """Session expiry in IST."""

    broker_name: str
    is_live: bool


class BrokerHealth(BaseModel):
    """Broker health status."""

    model_config = ConfigDict(strict=True, frozen=True)

    is_healthy: bool
    latency_ms: int
    last_checked: datetime
    """Last health check timestamp in IST."""

    session_valid: bool
    error_message: str | None = None


class OrderModification(BaseModel):
    """Order modification request."""

    model_config = ConfigDict(strict=True, frozen=True)

    order_id: str
    new_quantity: int | None = None
    new_price: Decimal | None = None
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reason must not be empty")
        return v


class BrokerConfig(BaseModel):
    """Configuration for a broker adapter."""

    model_config = ConfigDict(strict=True, frozen=True)

    broker_name: str
    base_url: str
    timeout_seconds: int = 30
    max_retries: int = 3
    dry_run: bool = True


class ShadowRunReport(BaseModel):
    """Report from a shadow-live EOD run."""

    model_config = ConfigDict(strict=True, frozen=True)

    trading_date: date
    regime_state: str
    candidates_scanned: int
    intents_generated: list[OrderIntent]
    orders_dry_run: list[OrderRecord]
    blockers_triggered: list[BlockerReport]
    audit_events_count: int
    completed_at: datetime
    """IST timestamp of completion."""

    errors: list[str]


class BrokerAuthError(Exception):
    """Raised when broker authentication fails."""

    def __init__(self, message: str = "Broker authentication failed") -> None:
        self.message = message
        super().__init__(message)


class BrokerNetworkError(Exception):
    """Raised on broker network timeout or connection error."""

    def __init__(self, message: str = "Broker network error") -> None:
        self.message = message
        super().__init__(message)


class LiveRunReport(BaseModel):
    """Report from a live EOD run, including post-close reconciliation."""

    model_config = ConfigDict(strict=True, frozen=False)

    trading_date: date
    mode: str
    orders_submitted: list[OrderRecord]
    orders_filled: list[OrderRecord]
    orders_cancelled: list[OrderRecord]
    positions_before: list[Position]
    positions_after: list[Position]
    reconciliation_result: ReconciliationReport
    risk_utilization: PortfolioRisk
    anomalies: list[str]
    reviewed_by_operator: bool = False
    review_notes: str | None = None
    generated_at: datetime


@runtime_checkable
class BrokerAdapter(Protocol):
    """Protocol that all broker adapters must implement.

    This is the single contract for broker interactions. Paper, mock,
    and live brokers all implement this interface identically.
    """

    async def authenticate(self) -> BrokerSession: ...

    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]: ...

    async def place_order(
        self, intent: OrderIntent, idempotency_key: str
    ) -> OrderRecord: ...

    async def modify_order(
        self, order_id: str, modification: OrderModification
    ) -> OrderRecord: ...

    async def cancel_order(
        self, order_id: str, reason: str
    ) -> OrderRecord: ...

    async def get_positions(self) -> list[Position]: ...

    async def get_orders(self, since: date) -> list[OrderRecord]: ...

    async def healthcheck(self) -> BrokerHealth: ...
