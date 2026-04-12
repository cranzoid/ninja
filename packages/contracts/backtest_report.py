"""Backtest report schema — full output of a historical simulation run."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from .eod_report import EODRunReport


class BacktestReport(BaseModel, frozen=True):
    """Full output of a historical simulation run."""

    model_config = ConfigDict(strict=True)

    run_id: str
    generated_at: datetime
    start_date: date
    end_date: date
    initial_equity: Decimal

    # Core performance
    final_equity: Decimal
    total_return_pct: Decimal
    nifty_return_pct: Decimal
    alpha_pct: Decimal

    # Drawdown
    max_drawdown_pct: Decimal
    max_drawdown_start: date
    max_drawdown_end: date

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal
    avg_win_pct: Decimal
    avg_loss_pct: Decimal
    profit_factor: Decimal

    # Regime breakdown
    trades_in_green_regime: int
    trades_in_mixed_regime: int
    trades_in_stressed_regime: int

    # Simulation health
    trading_days_run: int
    days_with_errors: int
    all_reconciliations_clean: bool

    # Raw data for charting
    equity_curve: list[tuple[date, Decimal]]
    daily_reports: list[EODRunReport]
