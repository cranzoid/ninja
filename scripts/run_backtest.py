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
import json
import os
import sys
import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

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
        import yfinance as yf

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
    audit_path: Path,
) -> tuple[int, int, int, Decimal, Decimal, Decimal, Decimal, int]:
    """Return trade statistics derived from the audit log.

    Tuple: (total_closed, wins, losses, win_rate_pct, avg_win, avg_loss,
            profit_factor, open_positions).

    Reads the audit JSONL files to pair entry fills with exit fills per symbol
    and compute real closed-trade P&L.
    """
    entry_order_ids: set[str] = set()
    exit_order_ids: set[str] = set()
    all_fills: list[dict[str, Any]] = []

    if audit_path.exists():
        for jsonl_file in sorted(audit_path.glob("audit_*.jsonl")):
            try:
                with open(jsonl_file) as fh:
                    for raw_line in fh:
                        raw_line = raw_line.strip()
                        if not raw_line:
                            continue
                        try:
                            event = json.loads(raw_line)
                        except json.JSONDecodeError:
                            continue
                        event_type = event.get("event_type", "")
                        payload = event.get("payload", {})
                        if event_type == "entry_order_submitted":
                            oid = payload.get("order_id")
                            if oid:
                                entry_order_ids.add(str(oid))
                        elif event_type == "exit_order_submitted":
                            oid = payload.get("order_id")
                            if oid:
                                exit_order_ids.add(str(oid))
                        elif event_type == "order_filled":
                            all_fills.append(
                                {
                                    "order_id": str(payload.get("order_id", "")),
                                    "symbol": str(payload.get("symbol", "")),
                                    "fill_price": Decimal(
                                        str(payload.get("fill_price", "0"))
                                    ),
                                    "filled_qty": int(payload.get("filled_qty", 0)),
                                }
                            )
            except Exception:
                continue

    # Tag fills and group by symbol (preserving chronological order)
    entry_fills_by_symbol: dict[str, list[dict[str, Any]]] = {}
    exit_fills_by_symbol: dict[str, list[dict[str, Any]]] = {}
    total_entry_fills = 0
    total_exit_fills = 0

    for fill in all_fills:
        oid = str(fill["order_id"])
        sym = str(fill["symbol"])
        if oid in entry_order_ids:
            entry_fills_by_symbol.setdefault(sym, []).append(fill)
            total_entry_fills += 1
        elif oid in exit_order_ids:
            exit_fills_by_symbol.setdefault(sym, []).append(fill)
            total_exit_fills += 1

    # Pair entry/exit fills per symbol and compute P&L
    wins = 0
    losses = 0
    gross_profit = Decimal("0")
    gross_loss = Decimal("0")

    for sym in set(entry_fills_by_symbol) | set(exit_fills_by_symbol):
        entries = entry_fills_by_symbol.get(sym, [])
        exits = exit_fills_by_symbol.get(sym, [])
        for entry_fill, exit_fill in zip(entries, exits, strict=False):
            entry_price = Decimal(str(entry_fill["fill_price"]))
            exit_price = Decimal(str(exit_fill["fill_price"]))
            qty = Decimal(
                str(min(int(entry_fill["filled_qty"]), int(exit_fill["filled_qty"])))
            )
            pnl = (exit_price - entry_price) * qty
            if pnl > 0:
                wins += 1
                gross_profit += pnl
            else:
                losses += 1
                gross_loss += abs(pnl)

    total_closed = wins + losses
    open_positions = max(0, total_entry_fills - total_exit_fills)

    win_rate = (
        (Decimal(str(wins)) / Decimal(str(total_closed)) * 100)
        if total_closed > 0
        else Decimal("0")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    avg_win = (
        (gross_profit / wins).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if wins > 0
        else Decimal("0")
    )
    avg_loss = (
        (gross_loss / losses).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if losses > 0
        else Decimal("0")
    )
    profit_factor = (
        (gross_profit / gross_loss).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if gross_loss > 0
        else Decimal("0")
    )

    return (
        total_closed,
        wins,
        losses,
        win_rate,
        avg_win,
        avg_loss,
        profit_factor,
        open_positions,
    )


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


def _print_summary(report: BacktestReport, open_positions: int = 0) -> None:
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
        f"  Closed trades:      {report.total_trades}"
        f"  ({report.winning_trades} wins / {report.losing_trades} losses)"
    )
    print(
        f"  Open at end:        {open_positions}"
        "  (positions never closed by simulation end)"
    )
    print(f"  Win rate:           {report.win_rate_pct:.0f}%")
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


async def _run(
    start: date, end: date, initial_equity: Decimal
) -> tuple[BacktestReport, int]:
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
        open_positions,
    ) = _calc_trade_stats(reports, tmp_dir / "audit")
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

    return report, open_positions


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

    report, open_positions = asyncio.run(
        _run(start=start, end=end, initial_equity=initial_equity)
    )
    _print_summary(report, open_positions)


if __name__ == "__main__":
    main()
