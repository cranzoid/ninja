"""CorporateAction schema — corporate action data for the corporate-action lane."""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class CorporateActionType(StrEnum):
    """Types of corporate actions that affect trading."""

    SPLIT = "split"
    BONUS = "bonus"
    RIGHTS = "rights"
    MERGER = "merger"
    DEMERGER = "demerger"


class CorporateAction(BaseModel):
    """
    A corporate action event for a symbol.

    Part of the corporate-action data lane (charter §9).
    Used by the universe loader to exclude symbols with unresolved actions,
    and by the blocker classifier to flag upcoming events.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    symbol: str
    action_type: CorporateActionType
    ex_date: date
    record_date: date
    ratio: Decimal | None = None
    details: str | None = None
    is_resolved: bool
