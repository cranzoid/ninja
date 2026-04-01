"""Fixture-based market data provider for development and testing."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .base import MarketDataProvider

DEFAULT_FIXTURES_DIR = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "market_data"
)


class FixtureMarketDataProvider(MarketDataProvider):
    """
    Reads OHLCV data from CSV files in a fixtures directory.

    CSV files are named {SYMBOL}.csv with columns:
    date, open, high, low, close, volume.
    """

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self.fixtures_dir = fixtures_dir or DEFAULT_FIXTURES_DIR

    async def fetch_ohlcv(
        self, symbol: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        csv_path = self.fixtures_dir / f"{symbol}.csv"
        if not csv_path.exists():
            cols = ["date", "open", "high", "low", "close", "volume"]
            return pd.DataFrame(columns=cols)

        df = pd.read_csv(csv_path, parse_dates=["date"])
        df["date"] = df["date"].dt.date

        mask = (df["date"] >= start_date) & (df["date"] <= end_date)
        return df.loc[mask].reset_index(drop=True)

    async def fetch_current_quote(self, symbol: str) -> dict[str, object]:
        csv_path = self.fixtures_dir / f"{symbol}.csv"
        if not csv_path.exists():
            return {"symbol": symbol, "price": 0.0, "volume": 0, "timestamp": None}

        df = pd.read_csv(csv_path, parse_dates=["date"])
        if df.empty:
            return {"symbol": symbol, "price": 0.0, "volume": 0, "timestamp": None}

        last_row = df.iloc[-1]
        return {
            "symbol": symbol,
            "price": float(last_row["close"]),
            "volume": int(last_row["volume"]),
            "timestamp": last_row["date"],
        }
