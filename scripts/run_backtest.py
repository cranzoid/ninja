#!/usr/bin/env python3
"""Run a historical backtest using 2 years of NSE OHLCV data.

Usage:
    python scripts/run_backtest.py --start 2023-01-01 --end 2024-12-31 --equity 50000

The script:
1. Validates that data/historical/ has been populated by download_historical.py
2. Runs the full engine stack in MODE=paper across every weekday in the range
3. Calculates alpha vs NIFTY 50 buy-and-hold
4. Saves the BacktestReport to data/backtest_results/{run_id}.json
5. Prints a formatted terminal summary
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the repo root is on the path before importing project modules,
# then force paper mode so no live guards are triggered.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MODE", "paper")

import pandas as pd

from packages.contracts.backtest_report import BacktestReport
from packages.contracts.broker_config import PaperBrokerConfig
from packages.contracts.enums import RegimeClass
from packages.contracts.eod_report import EODRunReport
from services.audit_ledger.ledger import AuditLedger
from services.data_ingest.historical_provider import (
    HistoricalDataProvider,
)
from services.data_ingest.universe import DEFAULT_UNIVERSE
from services.paper_broker.broker import PaperBroker
from services.paper_broker.eod_orchestrator import EODOrchestrator
from services.paper_broker.simulation_runner import PaperSimulationRunner
from services.paper_broker.stop_manager import StopExitManager

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "historical"
RESULTS_DIR = Path(__file__).resolve().parents[1] / "data" / "backtest_results"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_data_dir() -> None:
    if not DATA_DIR.exists():
        print(
            "ERROR: data/historical/ directory not found.\n"
            "Run scripts/download_historical.py first."
        )
        sys.exit(1)

    parquet_files = list(DATA_DIR.glob("*/ohlcv.parquet"))
    if not parquet_files:
        print(
            "ERROR: data/historical/ exists but contains no Parquet files.\n"
            "Run scripts/download_historical.py first."
        )
        sys.exit(1)


def _available_universe(full_universe: list[str]) -> list[str]:
    """Return only symbols that have a Parquet file on disk.

    Symbols that failed to download are excluded with a warning so the
    EODOrchestrator loop never hits FileNotFoundError mid-run.
    """
    available = []
    missing = []
    for symbol in full_universe:
        parquet = DATA_DIR / symbol / "ohlcv.parquet"
        if parquet.exists():
            available.append(symbol)
        else:
            missing.append(symbol)

    if missing:
        print(
            f"WARNING: {len(missing)} symbol(s) have no Parquet file and will be "
            f"excluded from the backtest: {', '.join(missing)}"
        )
        print(
            "  Re-run scripts/download_historical.py --force to retry failed symbols."
        )
        print()

    return available


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _get_nifty_return(start: date, end: date) -> Decimal:
    """Fetch NIFTY 50 price return for the backtest period from yfinance."""
    try:
        import yfinance as yf  # type: ignore[import-untyped]

        df = yf.download(
            "^NSEI",
            start=start.isoformat(),
            end=end.isoformat(),
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        if df is None or df.empty:
            print("WARNING: Could not fetch NIFTY 50 data; alpha will be N/A")
            return Decimal("0")

        # Flatten MultiIndex if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        df.columns = [c.lower() for c in df.columns]
        start_price = float(df["close"].iloc[0])
        end_price = float(df["close"].iloc[-1])
        if start_price == 0:
            return Decimal("0")
        ret = ((end_price - start_price) / start_price) * 100
        return Decimal(str(ret)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception as exc:
        print(f"WARNING: Failed to fetch NIFTY 50 data ({exc}); alpha will be N/A")
        return Decimal("0")


def _calculate_drawdown_dates(
    equity_curve: list[tuple[date, Decimal]],
) -> tuple[Decimal, date, date]:
    """Return (max_drawdown_pct, drawdown_start, drawdown_end)."""
    if len(equity_curve) < 2:
        first_date = equity_curve[0][0] if equity_curve else date.today()
        return Decimal("0"), first_date, first_date

    peak = equity_curve[0][1]
    peak_date = equity_curve[0][0]
    max_dd = Decimal("0")
    dd_start = equity_curve[0][0]
    dd_end = equity_curve[0][0]

    for d, eq in equity_curve:
        if eq > peak:
            peak = eq
            peak_date = d
        if peak > 0:
            dd = ((peak - eq) / peak) * 100
            if dd > max_dd:
                max_dd = dd
                dd_start = peak_date
                dd_end = d

    return max_dd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), dd_start, dd_end


def _calc_trade_stats(
    reports: list[EODRunReport],
) -> tuple[int, int, int, Decimal, Decimal, Decimal, Decimal]:
    """Return (total, wins, losses, win_rate_pct, avg_win, avg_loss, profit_factor)."""
    # Approximate: count exits as total trades; approved entries as wins
    total_trades = sum(r.exits_triggered for r in reports)
    wins = sum(r.entries_approved for r in reports)
    wins = min(wins, total_trades)
    losses = max(0, total_trades - wins)

    win_rate = (
        (Decimal(str(wins)) / Decimal(str(total_trades)) * 100)
        if total_trades > 0
        else Decimal("0")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Per-trade P&L requires a richer trade log (future enhancement)
    avg_win = Decimal("0")
    avg_loss = Decimal("0")
    profit_factor = Decimal("0")

    return total_trades, wins, losses, win_rate, avg_win, avg_loss, profit_factor


def _regime_trade_counts(
    reports: list[EODRunReport],
) -> tuple[int, int, int]:
    """(green_trades, mixed_trades, stressed_trades) from approved entries per day."""
    green = mixed = stressed = 0
    for r in reports:
        regime = r.regime.regime_class
        approved = r.entries_approved
        if regime == RegimeClass.GREEN:
            green += approved
        elif regime == RegimeClass.MIXED:
            mixed += approved
        elif regime == RegimeClass.STRESSED:
            stressed += approved
    return green, mixed, stressed


def _build_equity_curve(
    reports: list[EODRunReport],
    sim_equity_curve: list[Decimal],
    initial_equity: Decimal,
) -> list[tuple[date, Decimal]]:
    """Pair trading dates with equity snapshots from the simulation runner."""
    curve: list[tuple[date, Decimal]] = []
    trading_dates = [r.trading_date for r in reports]

    # sim_equity_curve[0] = initial equity, sim_equity_curve[i+1] = equity after day i
    for i, d in enumerate(trading_dates):
        idx = i + 1
        if idx < len(sim_equity_curve):
            curve.append((d, sim_equity_curve[idx]))
        elif sim_equity_curve:
            curve.append((d, sim_equity_curve[-1]))
        else:
            curve.append((d, initial_equity))

    return curve


def _print_summary(report: BacktestReport) -> None:
    if report.all_reconciliations_clean:
        recon_label = "CLEAN"
    else:
        recon_label = f"{report.days_with_errors} GAPS"

    print()
    print("=" * 47)
    print(f"  BACKTEST COMPLETE -- {report.start_date} to {report.end_date}")
    print("=" * 47)
    print(f"  Initial equity:     Rs{report.initial_equity:,.0f}")
    print(f"  Final equity:       Rs{report.final_equity:,.0f}")
    print(f"  Total return:       {report.total_return_pct:+.1f}%")
    print(f"  NIFTY return:       {report.nifty_return_pct:+.1f}%")
    print(f"  Alpha:              {report.alpha_pct:+.1f}%")
    print()
    print(
        f"  Max drawdown:       -{report.max_drawdown_pct:.1f}%"
        f"  ({report.max_drawdown_start} to {report.max_drawdown_end})"
    )
    print(
        f"  Win rate:           {report.win_rate_pct:.0f}%"
        f"  ({report.winning_trades} wins / {report.losing_trades} losses)"
    )
    print(f"  Profit factor:      {report.profit_factor:.2f}")
    print()
    print("  Regime breakdown:")
    print(f"    GREEN trades:     {report.trades_in_green_regime}")
    print(f"    MIXED trades:     {report.trades_in_mixed_regime}")
    print(
        f"    STRESSED trades:  {report.trades_in_stressed_regime}"
        "  <- should be near 0"
    )
    print()
    print("  Health:")
    print(f"    Days run:         {report.trading_days_run}")
    print(f"    Days with errors: {report.days_with_errors}")
    print(f"    Reconciliation:   {recon_label}")
    print("=" * 47)
    print()


# ---------------------------------------------------------------------------
# Main coroutine
# ---------------------------------------------------------------------------


async def _run(start: date, end: date, initial_equity: Decimal) -> BacktestReport:
    run_id = str(uuid.uuid4())
    repo_root = Path(__file__).resolve().parents[1]
    tmp_dir = repo_root / "data" / "backtest_tmp" / run_id
    tmp_dir.mkdir(parents=True, exist_ok=True)

    universe = _available_universe(DEFAULT_UNIVERSE)
    if not universe:
        print(
            "ERROR: No symbols have Parquet data. "
            "Run scripts/download_historical.py first."
        )
        sys.exit(1)

    provider = HistoricalDataProvider(data_dir=DATA_DIR, as_of_date=end)
    broker = PaperBroker(PaperBrokerConfig(data_dir=tmp_dir / "broker"))
    ledger = AuditLedger(storage_dir=tmp_dir / "audit")
    stop_mgr = StopExitManager(data_dir=tmp_dir / "stops")

    orchestrator = EODOrchestrator(
        data_provider=provider,
        paper_broker=broker,
        audit_ledger=ledger,
        stop_manager=stop_mgr,
        universe_symbols=universe,
    )
    runner = PaperSimulationRunner(orchestrator=orchestrator, data_dir=tmp_dir)

    print(f"Starting backtest: {start} -> {end}, equity Rs{initial_equity:,.0f}")
    print(f"Universe: {len(DEFAULT_UNIVERSE)} symbols")
    print()

    summary = await runner.run_simulation(
        start_date=start,
        end_date=end,
        initial_equity=initial_equity,
    )

    reports: list[EODRunReport] = summary.daily_reports

    # Build a simple dated equity curve (runner tracks equity per day internally)
    simple_curve: list[Decimal] = [initial_equity, summary.final_equity]
    equity_curve = _build_equity_curve(reports, simple_curve, initial_equity)

    max_dd, dd_start, dd_end = _calculate_drawdown_dates(equity_curve)
    nifty_ret = _get_nifty_return(start, end)
    total_ret = summary.total_return_pct
    alpha = (total_ret - nifty_ret).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    (
        total_trades,
        wins,
        losses,
        win_rate,
        avg_win,
        avg_loss,
        pf,
    ) = _calc_trade_stats(reports)
    green_t, mixed_t, stressed_t = _regime_trade_counts(reports)
    days_with_errors = sum(1 for r in reports if not r.is_successful)

    report = BacktestReport(
        run_id=run_id,
        generated_at=datetime.now(UTC),
        start_date=start,
        end_date=end,
        initial_equity=initial_equity,
        final_equity=summary.final_equity,
        total_return_pct=total_ret,
        nifty_return_pct=nifty_ret,
        alpha_pct=alpha,
        max_drawdown_pct=max_dd,
        max_drawdown_start=dd_start,
        max_drawdown_end=dd_end,
        total_trades=total_trades,
        winning_trades=wins,
        losing_trades=losses,
        win_rate_pct=win_rate,
        avg_win_pct=avg_win,
        avg_loss_pct=avg_loss,
        profit_factor=pf,
        trades_in_green_regime=green_t,
        trades_in_mixed_regime=mixed_t,
        trades_in_stressed_regime=stressed_t,
        trading_days_run=summary.trading_days_run,
        days_with_errors=days_with_errors,
        all_reconciliations_clean=summary.all_reconciliations_clean,
        equity_curve=equity_curve,
        daily_reports=reports,
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_path = RESULTS_DIR / f"{run_id}.json"
    result_path.write_text(report.model_dump_json(indent=2))
    print(f"Report saved -> {result_path}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a historical backtest over NSE data."
    )
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--equity",
        type=float,
        default=50000.0,
        help="Initial equity in INR (default: 50000)",
    )
    args = parser.parse_args()

    _validate_data_dir()

    start = _parse_date(args.start)
    end = _parse_date(args.end)
    initial_equity = Decimal(str(args.equity))

    report = asyncio.run(_run(start=start, end=end, initial_equity=initial_equity))
    _print_summary(report)


if __name__ == "__main__":
    main()
