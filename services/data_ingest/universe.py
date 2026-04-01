"""Universe loader — manages the tradeable symbol universe."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

# Default NIFTY 100 starter universe (top 25 liquid names)
DEFAULT_UNIVERSE: list[str] = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "BHARTIARTL",
    "ITC",
    "SBIN",
    "LT",
    "KOTAKBANK",
    "AXISBANK",
    "HINDUNILVR",
    "MARUTI",
    "TATAMOTORS",
    "SUNPHARMA",
    "WIPRO",
    "TITAN",
    "ULTRACEMCO",
    "BAJFINANCE",
    "NESTLEIND",
    "ADANIENT",
    "TECHM",
    "POWERGRID",
    "NTPC",
    "ONGC",
]


class UniverseConfig(BaseModel):
    """Configuration for the tradeable universe."""

    model_config = ConfigDict(strict=True, frozen=True)

    symbols: list[str] = list(DEFAULT_UNIVERSE)
    price_floor: Decimal = Decimal("100.00")
    liquidity_floor_avg_volume: int = 500_000
    exclude_symbols: list[str] = []


def load_universe(
    config: UniverseConfig,
    latest_prices: dict[str, Decimal] | None = None,
    latest_volumes: dict[str, int] | None = None,
) -> list[str]:
    """
    Return filtered symbol list from the configured universe.

    Applies exclusion list, price floor, and liquidity floor checks.
    If price/volume data is not provided, only exclusion filtering is applied.
    """
    prices = latest_prices or {}
    volumes = latest_volumes or {}

    filtered: list[str] = []
    for symbol in config.symbols:
        if symbol in config.exclude_symbols:
            continue

        # Check price floor if data available
        if symbol in prices and prices[symbol] < config.price_floor:
            continue

        # Check liquidity floor if data available
        if (
            symbol in volumes
            and volumes[symbol] < config.liquidity_floor_avg_volume
        ):
            continue

        filtered.append(symbol)

    return sorted(filtered)
