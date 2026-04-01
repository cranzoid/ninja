"""OHLCV storage — file-based storage using Parquet files."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd


def save_ohlcv(symbol: str, df: pd.DataFrame, data_dir: Path) -> Path:
    """
    Save OHLCV DataFrame as a Parquet file.

    Creates the data directory if it doesn't exist.
    Returns the path to the saved file.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{symbol}.parquet"

    # Ensure date column is datetime for parquet serialization
    save_df = df.copy()
    save_df["date"] = pd.to_datetime(save_df["date"])
    save_df.to_parquet(path, index=False)
    return path


def load_ohlcv(
    symbol: str,
    data_dir: Path,
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    """
    Load OHLCV data from a Parquet file, optionally filtered by date range.

    Returns DataFrame with columns: date, open, high, low, close, volume.
    Date column contains datetime.date objects.
    Returns empty DataFrame if file doesn't exist.
    """
    path = data_dir / f"{symbol}.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    if start_date is not None:
        df = df[df["date"] >= start_date]
    if end_date is not None:
        df = df[df["date"] <= end_date]

    return df.reset_index(drop=True)
