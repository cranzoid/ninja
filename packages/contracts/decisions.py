"""Decision schemas — output of the rule engine evaluators."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .enums import PortfolioLayer
from .order_intent import OrderIntent


class EntryDecision(BaseModel):
    """Result of evaluating a candidate for entry."""

    model_config = ConfigDict(strict=True, frozen=True)

    symbol: str
    layer: PortfolioLayer
    decision: Literal["approve", "reject"]
    order_intent: OrderIntent | None = None
    rejection_reasons: list[str]
    checks_performed: list[str]


class ExitDecision(BaseModel):
    """Result of evaluating a position for exit."""

    model_config = ConfigDict(strict=True, frozen=True)

    symbol: str
    layer: PortfolioLayer
    decision: Literal["exit_full", "exit_partial", "hold"]
    exit_reason: str | None = None
    order_intent: OrderIntent | None = None
