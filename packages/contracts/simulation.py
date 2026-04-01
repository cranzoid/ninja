"""Simulation summary schema — output of multi-day paper simulation runs."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from .eod_report import EODRunReport


class SimulationSummary(BaseModel):
    """Summary of a multi-day paper trading simulation."""

    model_config = ConfigDict(strict=True, frozen=False)

    simulation_id: str
    start_date: date
    end_date: date
    trading_days_run: int
    initial_equity: Decimal
    final_equity: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_return_pct: Decimal
    max_drawdown_pct: Decimal
    daily_reports: list[EODRunReport]
    all_reconciliations_clean: bool
    errors_encountered: list[str]
