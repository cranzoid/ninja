"""Tests for HistoricalDataProvider — Phase 3B.

All tests use small in-memory Parquet fixtures. No network calls.
No existing test files are modified.
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from services.data_ingest.historical_provider import HistoricalDataProvider

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_parquet(tmp_dir: Path, symbol: str, rows: list[dict]) -> None:
    """Write a minimal OHLCV Parquet file for a symbol."""
    symbol_dir = tmp_dir / symbol
    symbol_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df.to_parquet(symbol_dir / "ohlcv.parquet", index=False)


def _make_ten_day_fixture(tmp_dir: Path) -> None:
    """Create OHLCV rows for January 1-10 2023 for symbol TESTSYM."""
    rows = [
        {
            "date": f"2023-01-{day:02d}",
            "open": 100.0 + day,
            "high": 102.0 + day,
            "low": 99.0 + day,
            "close": 101.0 + day,
            "volume": 1_000_000 + day * 1000,
        }
        for day in range(1, 11)
    ]
    _make_parquet(tmp_dir, "TESTSYM", rows)


# ---------------------------------------------------------------------------
# test_as_of_date_filters_future_rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_as_of_date_filters_future_rows() -> None:
    """Only rows with date <= as_of_date must be returned."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        _make_ten_day_fixture(tmp_dir)

        as_of = date(2023, 1, 5)
        provider = HistoricalDataProvider(data_dir=tmp_dir, as_of_date=as_of)

        df = await provider.fetch_ohlcv(
            "TESTSYM",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 10),  # caller passes future end — should be capped
        )

        assert not df.empty, "Expected rows to be returned"
        assert all(
            row <= as_of for row in df["date"]
        ), "All returned rows must have date <= as_of_date"
        assert len(df) == 5, f"Expected exactly 5 rows (Jan 1-5), got {len(df)}"


# ---------------------------------------------------------------------------
# test_missing_file_raises_clear_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_file_raises_clear_error() -> None:
    """FileNotFoundError with guidance message when Parquet file is missing."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        provider = HistoricalDataProvider(
            data_dir=tmp_dir, as_of_date=date(2023, 12, 31)
        )

        with pytest.raises(FileNotFoundError) as exc_info:
            await provider.fetch_ohlcv(
                "NOSYMBOL",
                start_date=date(2023, 1, 1),
                end_date=date(2023, 12, 31),
            )

        assert "download_historical" in str(exc_info.value), (
            "Error message must mention download_historical"
        )


# ---------------------------------------------------------------------------
# test_returns_correct_columns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_correct_columns() -> None:
    """Returned DataFrame must have exactly the expected OHLCV columns."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        _make_ten_day_fixture(tmp_dir)

        provider = HistoricalDataProvider(
            data_dir=tmp_dir, as_of_date=date(2023, 12, 31)
        )
        df = await provider.fetch_ohlcv(
            "TESTSYM",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )

        expected_columns = {"date", "open", "high", "low", "close", "volume"}
        actual_columns = set(df.columns)
        assert expected_columns.issubset(actual_columns), (
            f"Missing columns: {expected_columns - actual_columns}"
        )


# ---------------------------------------------------------------------------
# test_start_date_filters_early_rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_date_filters_early_rows() -> None:
    """Rows before start_date must not be returned."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        _make_ten_day_fixture(tmp_dir)

        provider = HistoricalDataProvider(
            data_dir=tmp_dir, as_of_date=date(2023, 12, 31)
        )
        df = await provider.fetch_ohlcv(
            "TESTSYM",
            start_date=date(2023, 1, 6),
            end_date=date(2023, 1, 10),
        )

        assert all(row >= date(2023, 1, 6) for row in df["date"]), (
            "Rows before start_date must be excluded"
        )
        assert len(df) == 5, f"Expected 5 rows (Jan 6-10), got {len(df)}"


# ---------------------------------------------------------------------------
# test_fetch_current_quote_respects_as_of_date
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_current_quote_respects_as_of_date() -> None:
    """fetch_current_quote must return data as of as_of_date, not the latest row."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        _make_ten_day_fixture(tmp_dir)

        as_of = date(2023, 1, 3)
        provider = HistoricalDataProvider(data_dir=tmp_dir, as_of_date=as_of)
        quote = await provider.fetch_current_quote("TESTSYM")

        # close on Jan 3 = 101.0 + 3 = 104.0
        assert quote["price"] == pytest.approx(104.0), (
            "fetch_current_quote must return the close price on as_of_date"
        )
