"""Historical data provider — reads from local Parquet files for backtesting.

Used exclusively for backtesting (MODE=paper). Enforces strict as_of_date
to prevent lookahead bias.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .providers.base import MarketDataProvider


class HistoricalDataProvider(MarketDataProvider):
    """
    Reads from local Parquet files downloaded by scripts/download_historical.py.
    Used exclusively for backtesting (MODE=paper).

    KEY CONSTRAINT: as_of_date strictly enforced.
    When get_ohlcv(symbol, as_of_date=date(2023, 6, 15)) is called,
    only rows with date <= 2023-06-15 are returned.
    This prevents lookahead bias.

    Data directory layout:
        data_dir/{SYMBOL}/ohlcv.parquet

    If a symbol's Parquet file is missing, raises FileNotFoundError with
    instructions to run scripts/download_historical.py first.
    """

    def __init__(self, data_dir: Path, as_of_date: date) -> None:
        self._data_dir = data_dir
        self._as_of_date = as_of_date
        # Cache loaded DataFrames to avoid repeated disk reads per simulation day
        self._cache: dict[str, pd.DataFrame] = {}

    # ------------------------------------------------------------------
    # MarketDataProvider interface
    # ------------------------------------------------------------------

    async def fetch_ohlcv(
        self, symbol: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """
        Return OHLCV rows for symbol where start_date <= date <= effective_end.

        effective_end = min(end_date, self._as_of_date) — the stricter cap
        prevents lookahead regardless of what the caller passes for end_date.
        """
        df = self._load(symbol)

        effective_end = min(end_date, self._as_of_date)

        mask = (df["date"] >= start_date) & (df["date"] <= effective_end)
        return df.loc[mask].reset_index(drop=True)

    async def fetch_current_quote(self, symbol: str) -> dict[str, object]:
        """Return the last available row on or before as_of_date as a quote."""
        df = self._load(symbol)

        mask = df["date"] <= self._as_of_date
        available = df.loc[mask]

        if available.empty:
            return {"symbol": symbol, "price": 0.0, "volume": 0, "timestamp": None}

        last = available.iloc[-1]
        return {
            "symbol": symbol,
            "price": float(last["close"]),
            "volume": int(last["volume"]),
            "timestamp": last["date"],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self, symbol: str) -> pd.DataFrame:
        """Load and cache the Parquet file for symbol."""
        if symbol in self._cache:
            return self._cache[symbol]

        parquet_path = self._data_dir / symbol / "ohlcv.parquet"
        if not parquet_path.exists():
            raise FileNotFoundError(
                f"No historical data found for {symbol} at {parquet_path}. "
                f"Run scripts/download_historical.py first to download data."
            )

        df = pd.read_parquet(parquet_path)

        # Normalise column names (tolerant of minor casing differences)
        df.columns = [c.lower() for c in df.columns]

        # Ensure date column is python date objects, not datetime
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.date
        elif df.index.name == "date":
            df = df.reset_index()
            df["date"] = pd.to_datetime(df["date"]).dt.date

        # Enforce dtypes
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = df[col].astype(float)
        if "volume" in df.columns:
            df["volume"] = df["volume"].astype("int64")

        df = df.sort_values("date").reset_index(drop=True)
        self._cache[symbol] = df
        return df
