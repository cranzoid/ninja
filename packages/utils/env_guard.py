"""EnvironmentGuard — runtime mode assertions to prevent accidental live execution.

Called at the start of any operation that must never run in live mode.
"""

from __future__ import annotations

import os

from packages.contracts.enums import Mode


class EnvironmentGuard:
    """Runtime assertions for environment mode safety."""

    def get_mode(self) -> Mode:
        """Read MODE from environment."""
        raw = os.environ.get("MODE", "paper")
        return Mode(raw)

    def is_armed_live(self) -> bool:
        """Check if ARMED_LIVE is set to true."""
        return os.environ.get("ARMED_LIVE", "false").lower() == "true"

    def assert_paper_mode(self) -> None:
        """Raise OSError if MODE is not paper."""
        mode = self.get_mode()
        if mode != Mode.PAPER:
            raise OSError(
                f"Operation requires paper mode, but MODE={mode.value}"
            )

    def assert_not_live(self) -> None:
        """Raise OSError if MODE is live AND ARMED_LIVE is true.

        This allows paper and shadow-live modes, but blocks live+armed.
        Shadow-live is safe because the broker adapter is always dry-run.
        """
        mode = self.get_mode()
        armed = self.is_armed_live()
        if mode == Mode.LIVE and armed:
            raise OSError(
                "Operation blocked: MODE=live and ARMED_LIVE=true. "
                "This operation is not allowed in armed live mode."
            )
