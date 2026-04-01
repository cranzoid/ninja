"""Reconciliation report schema."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ReconciliationReport(BaseModel):
    """Result of reconciling broker state against audit trail."""

    model_config = ConfigDict(strict=True, frozen=True)

    reconciled_at: datetime
    target_date: date
    positions_match: bool
    orders_match: bool
    position_mismatches: list[str]
    order_mismatches: list[str]
    unmatched_intents: list[str]
    orphan_fills: list[str]
    is_clean: bool
