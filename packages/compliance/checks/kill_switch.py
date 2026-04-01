"""KillSwitchCheck — verifies KILL_SWITCH is not active."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from packages.contracts.compliance import (
    ComplianceContext,
    ComplianceResult,
    ComplianceStatus,
)
from packages.contracts.enums import Mode


class KillSwitchCheck:
    """Verifies KILL_SWITCH env var is not set to 'true'."""

    name: str = "kill_switch"
    description: str = "Kill switch is not active"
    blocking: bool = True

    async def run(self, context: ComplianceContext) -> ComplianceResult:
        now = datetime.now(UTC)

        if context.mode == Mode.PAPER:
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.SKIPPED,
                message="Kill switch check skipped in paper mode.",
                checked_at=now,
            )

        kill_switch = os.environ.get("KILL_SWITCH", "false").lower()
        if kill_switch == "true":
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.FAIL,
                message="Kill switch is active — live arming blocked.",
                checked_at=now,
            )

        return ComplianceResult(
            check_name=self.name,
            status=ComplianceStatus.PASS,
            message="Kill switch is not active.",
            checked_at=now,
        )
