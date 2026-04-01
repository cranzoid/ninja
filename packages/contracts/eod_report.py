"""EOD run report schema."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from .enums import Mode
from .reconciliation import ReconciliationReport
from .regime_state import RegimeState
from .risk import PortfolioRisk


class EODRunReport(BaseModel):
    """Report produced by the EOD orchestrator for one trading day."""

    model_config = ConfigDict(strict=True, frozen=False)

    run_id: str
    trading_date: date
    mode: Mode
    started_at: datetime
    completed_at: datetime
    regime: RegimeState
    candidates_scanned: int
    swing_candidates_passing: int
    core_candidates_passing: int
    entries_approved: int
    entries_rejected: int
    exits_triggered: int
    orders_filled: int
    portfolio_risk: PortfolioRisk
    reconciliation: ReconciliationReport
    errors: list[str]
    is_successful: bool
