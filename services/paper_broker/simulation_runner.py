"""Paper simulation runner — runs the EOD orchestrator across multiple days.

Charter section 14.1: "Stable multi-week paper runs without silent failures."
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from packages.contracts.eod_report import EODRunReport
from packages.contracts.simulation import SimulationSummary

from .eod_orchestrator import EODOrchestrator

logger = logging.getLogger(__name__)


class PaperSimulationRunner:
    """
    Runs the paper trading system across a date range.
    Charter section 14.1: "Stable multi-week paper runs without silent failures."
    """

    def __init__(self, orchestrator: EODOrchestrator, data_dir: Path) -> None:
        self._orchestrator = orchestrator
        self._data_dir = data_dir

    async def run_simulation(
        self,
        start_date: date,
        end_date: date,
        initial_equity: Decimal,
    ) -> SimulationSummary:
        """Run the paper trading system across a date range."""
        simulation_id = str(uuid.uuid4())
        sim_dir = self._data_dir / f"simulation_{simulation_id}"
        sim_dir.mkdir(parents=True, exist_ok=True)

        # Initialize broker with starting cash
        self._orchestrator._broker.set_cash(initial_equity)

        # Determine trading days (skip weekends for now)
        trading_days = _get_trading_days(start_date, end_date)

        daily_reports: list[EODRunReport] = []
        errors: list[str] = []
        equity_curve: list[Decimal] = [initial_equity]

        for day in trading_days:
            logger.info("Running EOD for %s", day)
            try:
                report = await self._orchestrator.run_eod(day)
                daily_reports.append(report)

                if report.errors:
                    errors.extend(
                        f"{day}: {e}" for e in report.errors
                    )

                # Track equity: cash + position values
                positions = await self._orchestrator._broker.get_positions()
                pos_value = sum(
                    p.current_price * p.quantity for p in positions
                )
                current_equity = self._orchestrator._broker.cash + pos_value
                equity_curve.append(current_equity)

            except Exception as e:
                error_msg = f"{day}: orchestrator_crash: {e}"
                errors.append(error_msg)
                logger.exception("EOD crashed for %s", day)

        # Calculate summary statistics
        final_equity = equity_curve[-1] if equity_curve else initial_equity
        total_return_pct = (
            ((final_equity - initial_equity) / initial_equity * 100)
            if initial_equity > 0
            else Decimal("0")
        ).quantize(Decimal("0.01"))

        max_drawdown_pct = _calculate_max_drawdown(equity_curve)

        # Count trades from orders
        all_orders = await self._orchestrator._broker.get_orders()
        filled_orders = [
            o for o in all_orders if o.current_status.value == "filled"
        ]
        total_trades = len(filled_orders)

        # Approximate winning/losing from sell orders
        winning = 0
        losing = 0
        for order in filled_orders:
            if order.intent.side.value == "sell" and order.fill_price is not None:
                if order.fill_price > order.intent.stop_price:
                    winning += 1
                else:
                    losing += 1

        all_clean = all(
            r.reconciliation.is_clean for r in daily_reports
        ) if daily_reports else True

        # Save reports
        for report in daily_reports:
            report_path = sim_dir / f"report_{report.trading_date}.json"
            report_path.write_text(report.model_dump_json(indent=2))

        summary = SimulationSummary(
            simulation_id=simulation_id,
            start_date=start_date,
            end_date=end_date,
            trading_days_run=len(daily_reports),
            initial_equity=initial_equity,
            final_equity=final_equity,
            total_trades=total_trades,
            winning_trades=winning,
            losing_trades=losing,
            total_return_pct=total_return_pct,
            max_drawdown_pct=max_drawdown_pct,
            daily_reports=daily_reports,
            all_reconciliations_clean=all_clean,
            errors_encountered=errors,
        )

        # Save summary
        summary_path = sim_dir / "summary.json"
        summary_path.write_text(summary.model_dump_json(indent=2))

        return summary


def _get_trading_days(start: date, end: date) -> list[date]:
    """Get weekdays between start and end (inclusive)."""
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon-Fri
            days.append(current)
        current += timedelta(days=1)
    return days


def _calculate_max_drawdown(equity_curve: list[Decimal]) -> Decimal:
    """Calculate maximum drawdown percentage from equity curve."""
    if len(equity_curve) < 2:
        return Decimal("0")

    peak = equity_curve[0]
    max_dd = Decimal("0")

    for eq in equity_curve:
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = ((peak - eq) / peak) * 100
            if dd > max_dd:
                max_dd = dd

    return max_dd.quantize(Decimal("0.01"))
