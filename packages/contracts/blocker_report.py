"""BlockerReport schema — structured output from the blocker classifier AI role."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from .enums import BlockerCategory


class BlockerDetail(BaseModel):
    """A single identified blocker for a symbol."""

    model_config = ConfigDict(strict=True, frozen=True)

    category: BlockerCategory

    severity: Literal["hard", "soft"]
    """hard = absolute block. soft = flag for operator review."""

    reason: str
    """1-2 sentence explanation of the blocker."""

    source_category: str
    """Data source category, e.g. 'earnings_calendar', 'news_feed'."""

    expires_at: datetime | None = None
    """When this blocker expires. None = indefinite."""


class BlockerReport(BaseModel):
    """
    Blocker scan result for a shortlisted symbol.

    Output of the blocker classifier AI role (charter §7.2).
    Run for every shortlisted name before rule engine evaluation.
    """

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "symbol": "INFY",
                    "scan_timestamp": "2026-03-26T09:15:00Z",
                    "blockers_found": [],
                    "is_blocked": False,
                    "model_provider": "anthropic",
                    "model_id": "claude-haiku-4-5",
                },
                {
                    "symbol": "HDFCBANK",
                    "scan_timestamp": "2026-03-26T09:15:00Z",
                    "blockers_found": [
                        {
                            "category": "earnings_window",
                            "severity": "hard",
                            "reason": "Q4 results in 5 days. Blocked per rule S1.",
                            "source_category": "earnings_calendar",
                            "expires_at": "2026-03-31T00:00:00Z",
                        }
                    ],
                    "is_blocked": True,
                    "model_provider": "anthropic",
                    "model_id": "claude-haiku-4-5",
                },
            ]
        },
    )

    symbol: str
    scan_timestamp: datetime

    blockers_found: list[BlockerDetail]
    """All identified blockers. Empty list = clean scan."""

    is_blocked: bool
    """True if and only if any hard blocker is present."""

    model_provider: str
    model_id: str

    @model_validator(mode="after")
    def validate_is_blocked(self) -> "BlockerReport":
        expected = any(b.severity == "hard" for b in self.blockers_found)
        if self.is_blocked != expected:
            raise ValueError(
                f"is_blocked must be {expected} based on blockers_found "
                f"(True only when a hard blocker is present)"
            )
        return self
