"""ModeFlagCheck — verifies MODE env var matches AppState configuration."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from packages.contracts.compliance import (
    ComplianceContext,
    ComplianceResult,
    ComplianceStatus,
)
from packages.contracts.enums import Mode


class ModeFlagCheck:
    """Verifies MODE env var matches the running configuration."""

    name: str = "mode_flag"
    description: str = "MODE env var matches running configuration"
    blocking: bool = True

    async def run(self, context: ComplianceContext) -> ComplianceResult:
        now = datetime.now(UTC)

        env_mode = os.environ.get("MODE", "paper")
        env_armed = os.environ.get("ARMED_LIVE", "false").lower() == "true"

        # Paper mode with ARMED_LIVE=true is a misconfiguration
        if env_mode == Mode.PAPER.value and env_armed:
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.FAIL,
                message="Misconfiguration: MODE=paper but ARMED_LIVE=true.",
                checked_at=now,
            )

        # Live mode with dry_run=True is inconsistent (warning, not blocking)
        if env_mode == Mode.LIVE.value and context.broker_config.dry_run:
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.WARNING,
                message="Inconsistency: MODE=live but broker dry_run=True.",
                checked_at=now,
            )

        return ComplianceResult(
            check_name=self.name,
            status=ComplianceStatus.PASS,
            message=f"Mode flag consistent: MODE={env_mode}, ARMED_LIVE={env_armed}.",
            checked_at=now,
        )
