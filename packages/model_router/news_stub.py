"""Stub news/headlines provider — placeholder for real news integration."""

from __future__ import annotations

# Canned neutral headlines per symbol
_CANNED_HEADLINES: dict[str, list[str]] = {
    "RELIANCE": [
        "Reliance Industries posts steady quarterly revenue growth",
        "RIL retail arm expands store footprint across tier-2 cities",
        "Jio Platforms announces 5G rollout progress update",
    ],
    "TCS": [
        "TCS wins multi-year digital transformation deal in Europe",
        "IT sector hiring outlook remains cautious for Q1 FY27",
        "TCS quarterly attrition rate stabilises at industry lows",
    ],
    "INFY": [
        "Infosys maintains FY27 revenue guidance at annual meet",
        "Infosys launches new AI-powered enterprise platform",
        "IT majors see stable demand from BFSI vertical",
    ],
    "HDFCBANK": [
        "HDFC Bank reports healthy loan book growth in Q4",
        "Banking sector credit growth remains strong at 15% YoY",
        "HDFC Bank branch expansion on track post-merger integration",
    ],
    "SBIN": [
        "SBI advances digital banking push with new mobile features",
        "Public sector banks report improved asset quality metrics",
        "SBI announces plans for green bond issuance",
    ],
}

_DEFAULT_HEADLINES = [
    "Markets trade in a narrow range amid mixed global cues",
    "Institutional buying supports key index constituents",
    "No significant corporate announcements reported",
]


class StubNewsProvider:
    """Returns canned neutral headlines per symbol.

    Placeholder — real news integration is post-Phase 5.
    """

    async def get_headlines(self, symbol: str) -> list[str]:
        """Return 3 canned neutral headlines for a symbol."""
        return _CANNED_HEADLINES.get(symbol, _DEFAULT_HEADLINES)
