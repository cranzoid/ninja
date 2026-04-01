"""Stub blocker provider — returns empty BlockerReports for paper mode.

Real blocker providers come in Phase 5 (model routing).
"""

from __future__ import annotations

from datetime import UTC, datetime

from packages.contracts.blocker_report import BlockerReport


class StubBlockerProvider:
    """Returns empty BlockerReports for all symbols in paper mode."""

    async def scan_blockers(self, symbol: str) -> BlockerReport:
        return BlockerReport(
            symbol=symbol,
            scan_timestamp=datetime.now(UTC),
            blockers_found=[],
            is_blocked=False,
            model_provider="stub",
            model_id="paper-mode-stub",
        )
