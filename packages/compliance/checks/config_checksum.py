"""ConfigChecksumCheck — verifies config checksum matches.

Phase 7: Now blocking=True. In live mode, checksum mismatch or missing
checksum env var blocks arming. In shadow-live: WARNING only. In paper: SKIPPED.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from packages.contracts.compliance import (
    ComplianceContext,
    ComplianceResult,
    ComplianceStatus,
)
from packages.contracts.enums import Mode


class ConfigChecksumCheck:
    """Computes SHA256 of current config and compares against CONFIG_CHECKSUM env."""

    name: str = "config_checksum"
    description: str = "Config checksum matches expected value"
    blocking: bool = True  # Phase 7: now blocking in live mode

    async def run(self, context: ComplianceContext) -> ComplianceResult:
        now = datetime.now(UTC)

        # Paper mode: skip entirely
        if context.mode == Mode.PAPER:
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.SKIPPED,
                message="Config checksum check skipped in paper mode.",
                checked_at=now,
            )

        expected_checksum = os.environ.get("CONFIG_CHECKSUM")

        # Live mode: missing checksum env var is a FAIL (blocks arming)
        if context.mode == Mode.LIVE:
            if expected_checksum is None:
                return ComplianceResult(
                    check_name=self.name,
                    status=ComplianceStatus.FAIL,
                    message="CONFIG_CHECKSUM env var not set — required in live mode.",
                    checked_at=now,
                )

            if context.config_checksum is None:
                return ComplianceResult(
                    check_name=self.name,
                    status=ComplianceStatus.FAIL,
                    message="No config checksum available in context.",
                    checked_at=now,
                )

            if context.config_checksum != expected_checksum:
                return ComplianceResult(
                    check_name=self.name,
                    status=ComplianceStatus.FAIL,
                    message=(
                        f"Config checksum mismatch: "
                        f"current={context.config_checksum[:16]}... "
                        f"expected={expected_checksum[:16]}..."
                    ),
                    checked_at=now,
                )

            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.PASS,
                message="Config checksum matches.",
                checked_at=now,
            )

        # Shadow-live mode: WARNING on mismatch or missing, not blocking
        if expected_checksum is None:
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.WARNING,
                message="CONFIG_CHECKSUM env var not set.",
                checked_at=now,
            )

        if context.config_checksum is None:
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.WARNING,
                message="No config checksum available in context.",
                checked_at=now,
            )

        if context.config_checksum != expected_checksum:
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.WARNING,
                message=(
                    f"Config checksum mismatch: "
                    f"current={context.config_checksum[:16]}... "
                    f"expected={expected_checksum[:16]}..."
                ),
                checked_at=now,
            )

        return ComplianceResult(
            check_name=self.name,
            status=ComplianceStatus.PASS,
            message="Config checksum matches.",
            checked_at=now,
        )
