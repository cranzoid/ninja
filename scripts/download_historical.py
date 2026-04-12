#!/usr/bin/env python3
"""Download 2 years of historical OHLCV data for the NSE universe.

Usage:
    python scripts/download_historical.py [--force]

Saves each symbol to data/historical/{SYMBOL}/ohlcv.parquet.
Pass --force to re-download symbols that already have a Parquet file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the repo root is on the path before importing project modules
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.data_ingest.universe import DEFAULT_UNIVERSE

START_DATE = "2023-01-01"
END_DATE = "2024-12-31"
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "historical"


def _nse_ticker(symbol: str) -> str:
    return f"{symbol}.NS"


def download_symbol(symbol: str, force: bool) -> int | None:
    """Download one symbol. Returns row count on success, None on failure."""
    import pandas as pd
    import yfinance as yf  # type: ignore[import-untyped]

    out_dir = DATA_DIR / symbol
    out_path = out_dir / "ohlcv.parquet"

    if out_path.exists() and not force:
        return -1  # Sentinel: already exists, skipped

    ticker = _nse_ticker(symbol)
    try:
        df = yf.download(
            ticker,
            start=START_DATE,
            end=END_DATE,
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
    except Exception as exc:
        print(f"  WARNING: yfinance raised an exception for {symbol}: {exc}")
        return None

    if df is None or df.empty:
        print(f"  WARNING: yfinance returned empty data for {symbol} ({ticker})")
        return None

    # Flatten MultiIndex columns that yfinance sometimes produces
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    # Rename columns to our standard names (case-insensitive)
    col_map = {c: c.lower() for c in df.columns}
    df = df.rename(columns=col_map)

    # yfinance uses a DatetimeIndex named "Date" or "Datetime"
    df = df.reset_index()
    date_col = next(
        (c for c in df.columns if c.lower() in ("date", "datetime")), None
    )
    if date_col is None:
        print(f"  WARNING: cannot find date column for {symbol}")
        return None

    df = df.rename(columns={date_col: "date"})
    df["date"] = df["date"].dt.date  # convert to python date

    # Keep only required columns
    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"  WARNING: missing columns {missing} for {symbol}")
        return None

    df = df[required].copy()
    df["open"] = df["open"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["close"] = df["close"].astype(float)
    df["volume"] = df["volume"].astype("int64")
    df = df.sort_values("date").reset_index(drop=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    return len(df)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download historical OHLCV data for the NSE universe."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if Parquet file already exists.",
    )
    args = parser.parse_args()

    symbols = DEFAULT_UNIVERSE
    total = len(symbols)
    succeeded = 0
    failed = 0
    skipped = 0
    total_rows = 0

    print(f"Downloading {total} symbols: {START_DATE} -> {END_DATE}")
    print(f"Output directory: {DATA_DIR}")
    print()

    for idx, symbol in enumerate(symbols, start=1):
        prefix = f"[{idx}/{total}] {symbol}"
        result = download_symbol(symbol, force=args.force)

        if result == -1:
            print(f"{prefix} — skipped (already exists, use --force to re-download)")
            skipped += 1
        elif result is None:
            print(f"{prefix} — FAILED")
            failed += 1
        else:
            print(f"{prefix} — downloaded {result} rows")
            succeeded += 1
            total_rows += result

    print()
    print("=" * 50)
    print(f"Done. Succeeded: {succeeded}  Failed: {failed}  Skipped: {skipped}")
    print(f"Total rows downloaded: {total_rows:,}")
    print("=" * 50)

    if failed > 0:
        print(
            f"\nWARNING: {failed} symbol(s) failed. "
            "Check your internet connection or try --force."
        )


if __name__ == "__main__":
    main()
