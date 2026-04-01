"""Abstract base for market data providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class MarketDataProvider(ABC):
    """
    Abstract market data provider.

    All market data access goes through this interface, allowing
    fixture/mock providers for development and real providers for production.
    """

    @abstractmethod
    async def fetch_ohlcv(
        self, symbol: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for a symbol over a date range.

        Returns DataFrame with columns: date, open, high, low, close, volume.
        Dates are datetime.date objects. Prices are float.
        """
        ...

    @abstractmethod
    async def fetch_current_quote(self, symbol: str) -> dict[str, object]:
        """
        Fetch the latest quote for a symbol.

        Returns dict with keys: symbol, price, volume, timestamp.
        """
        ...
