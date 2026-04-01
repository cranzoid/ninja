"""BrokerAuthCheck — verifies broker authentication works."""

from __future__ import annotations

from datetime import UTC, datetime

from packages.contracts.broker import BrokerAdapter, BrokerAuthError
from packages.contracts.compliance import (
    ComplianceContext,
    ComplianceResult,
    ComplianceStatus,
)
from packages.contracts.enums import Mode


class BrokerAuthCheck:
    """Verifies broker authentication succeeds."""

    name: str = "broker_auth"
    description: str = "Broker authentication is valid"
    blocking: bool = True

    def __init__(self, broker_adapter: BrokerAdapter | None = None) -> None:
        self._broker = broker_adapter

    async def run(self, context: ComplianceContext) -> ComplianceResult:
        now = datetime.now(UTC)

        if context.mode == Mode.PAPER:
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.SKIPPED,
                message="Broker auth check skipped in paper mode.",
                checked_at=now,
            )

        if self._broker is None:
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.FAIL,
                message="No broker adapter configured.",
                checked_at=now,
            )

        try:
            auth_fn = self._broker.authenticate
            session = await auth_fn()
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.PASS,
                message=(
                    f"Broker auth successful. "
                    f"Session expires at {session.expires_at.isoformat()}."
                ),
                checked_at=now,
            )
        except BrokerAuthError as e:
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.FAIL,
                message=f"Broker auth failed: {e.message}",
                checked_at=now,
            )
