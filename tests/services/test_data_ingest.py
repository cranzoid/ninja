"""Tests for the data ingest service."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from services.data_ingest.providers.fixture_provider import FixtureMarketDataProvider
from services.data_ingest.storage import load_ohlcv, save_ohlcv
from services.data_ingest.universe import UniverseConfig, load_universe

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "market_data"


# --- Universe tests ---


class TestUniverseLoader:
    def test_load_default_universe(self) -> None:
        config = UniverseConfig()
        result = load_universe(config)
        assert len(result) == 25
        assert "RELIANCE" in result
        assert "TCS" in result

    def test_exclude_symbols(self) -> None:
        config = UniverseConfig(exclude_symbols=["RELIANCE", "TCS"])
        result = load_universe(config)
        assert "RELIANCE" not in result
        assert "TCS" not in result
        assert len(result) == 23

    def test_price_floor_filter(self) -> None:
        config = UniverseConfig(
            symbols=["RELIANCE", "TCS", "PENNY"],
            price_floor=Decimal("100.00"),
        )
        prices = {
            "RELIANCE": Decimal("2600"),
            "TCS": Decimal("4000"),
            "PENNY": Decimal("50"),
        }
        result = load_universe(config, latest_prices=prices)
        assert "RELIANCE" in result
        assert "TCS" in result
        assert "PENNY" not in result

    def test_liquidity_floor_filter(self) -> None:
        config = UniverseConfig(
            symbols=["RELIANCE", "ILLIQUID"],
            liquidity_floor_avg_volume=500_000,
        )
        volumes = {"RELIANCE": 15_000_000, "ILLIQUID": 100_000}
        result = load_universe(config, latest_volumes=volumes)
        assert "RELIANCE" in result
        assert "ILLIQUID" not in result

    def test_sorted_output(self) -> None:
        config = UniverseConfig(symbols=["TCS", "RELIANCE", "INFY"])
        result = load_universe(config)
        assert result == sorted(result)


# --- Fixture provider tests ---


class TestFixtureProvider:
    def test_fetch_ohlcv_returns_correct_shape(self) -> None:
        provider = FixtureMarketDataProvider(FIXTURES_DIR)
        df = asyncio.get_event_loop().run_until_complete(
            provider.fetch_ohlcv("RELIANCE", date(2025, 3, 1), date(2026, 3, 1))
        )
        assert not df.empty
        expected_cols = {"date", "open", "high", "low", "close", "volume"}
        assert set(df.columns) == expected_cols

    def test_fetch_ohlcv_date_filtering(self) -> None:
        provider = FixtureMarketDataProvider(FIXTURES_DIR)
        start = date(2025, 6, 1)
        end = date(2025, 6, 30)
        df = asyncio.get_event_loop().run_until_complete(
            provider.fetch_ohlcv("RELIANCE", start, end)
        )
        assert not df.empty
        for d in df["date"]:
            assert d >= start
            assert d <= end

    def test_fetch_ohlcv_missing_symbol(self) -> None:
        provider = FixtureMarketDataProvider(FIXTURES_DIR)
        df = asyncio.get_event_loop().run_until_complete(
            provider.fetch_ohlcv("NONEXISTENT", date(2025, 1, 1), date(2025, 12, 31))
        )
        assert df.empty

    def test_fetch_current_quote(self) -> None:
        provider = FixtureMarketDataProvider(FIXTURES_DIR)
        quote = asyncio.get_event_loop().run_until_complete(
            provider.fetch_current_quote("RELIANCE")
        )
        assert quote["symbol"] == "RELIANCE"
        assert isinstance(quote["price"], float)
        assert quote["price"] > 0


# --- Storage tests ---


class TestStorage:
    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        df = pd.DataFrame({
            "date": [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)],
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [99.0, 100.0, 101.0],
            "close": [103.0, 104.0, 105.0],
            "volume": [1000000, 1100000, 1200000],
        })

        path = save_ohlcv("TEST", df, tmp_path)
        assert path.exists()

        loaded = load_ohlcv("TEST", tmp_path)
        assert len(loaded) == 3
        expected_cols = ["date", "open", "high", "low", "close", "volume"]
        assert list(loaded.columns) == expected_cols
        assert loaded.iloc[0]["close"] == pytest.approx(103.0)

    def test_load_with_date_range(self, tmp_path: Path) -> None:
        df = pd.DataFrame({
            "date": [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)],
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [99.0, 100.0, 101.0],
            "close": [103.0, 104.0, 105.0],
            "volume": [1000000, 1100000, 1200000],
        })
        save_ohlcv("TEST", df, tmp_path)

        loaded = load_ohlcv("TEST", tmp_path, start_date=date(2025, 1, 3))
        assert len(loaded) == 2

        loaded = load_ohlcv("TEST", tmp_path, end_date=date(2025, 1, 3))
        assert len(loaded) == 2

    def test_load_nonexistent_symbol(self, tmp_path: Path) -> None:
        loaded = load_ohlcv("NONEXISTENT", tmp_path)
        assert loaded.empty
