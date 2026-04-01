"""yfinance-based market data provider for production use.

NOTE: This provider requires network access to fetch data from Yahoo Finance.
It appends .NS suffix for NSE symbols. Use FixtureMarketDataProvider for
development and testing environments without network access.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from .base import MarketDataProvider


class YFinanceMarketDataProvider(MarketDataProvider):
    """
    Wraps yfinance to fetch NSE market data.

    Requires network access. Appends .NS suffix to symbol names
    for NSE-listed stocks on Yahoo Finance.
    """

    def _nse_ticker(self, symbol: str) -> str:
        return f"{symbol}.NS"

    async def fetch_ohlcv(
        self, symbol: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        import yfinance as yf

        ticker = yf.Ticker(self._nse_ticker(symbol))
        df = ticker.history(
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            auto_adjust=True,
        )

        if df.empty:
            return pd.DataFrame(
                columns=["date", "open", "high", "low", "close", "volume"]
            )

        df = df.reset_index()
        df = df.rename(columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df[["date", "open", "high", "low", "close", "volume"]].reset_index(
            drop=True
        )

    async def fetch_current_quote(self, symbol: str) -> dict[str, object]:
        import yfinance as yf

        ticker = yf.Ticker(self._nse_ticker(symbol))
        info = ticker.info
        return {
            "symbol": symbol,
            "price": float(info.get("currentPrice", 0.0)),
            "volume": int(info.get("volume", 0)),
            "timestamp": info.get("regularMarketTime"),
        }
