"""BrokerHealthCheck — verifies broker is healthy and responsive."""

from __future__ import annotations

from datetime import UTC, datetime

from packages.contracts.broker import BrokerAdapter
from packages.contracts.compliance import (
    ComplianceContext,
    ComplianceResult,
    ComplianceStatus,
)
from packages.contracts.enums import Mode


class BrokerHealthCheck:
    """Verifies broker adapter reports healthy status."""

    name: str = "broker_health"
    description: str = "Broker is healthy and responsive"
    blocking: bool = True

    def __init__(self, broker_adapter: BrokerAdapter | None = None) -> None:
        self._broker = broker_adapter

    async def run(self, context: ComplianceContext) -> ComplianceResult:
        now = datetime.now(UTC)

        if context.mode == Mode.PAPER:
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.SKIPPED,
                message="Broker health check skipped in paper mode.",
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
            hc_fn = self._broker.healthcheck
            health = await hc_fn()
            if not health.is_healthy:
                return ComplianceResult(
                    check_name=self.name,
                    status=ComplianceStatus.FAIL,
                    message=f"Broker unhealthy: {health.error_message or 'no details'}",
                    checked_at=now,
                )
            if health.latency_ms > 2000:
                return ComplianceResult(
                    check_name=self.name,
                    status=ComplianceStatus.WARNING,
                    message=f"Broker healthy but high latency: {health.latency_ms}ms",
                    checked_at=now,
                )
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.PASS,
                message=f"Broker healthy. Latency: {health.latency_ms}ms.",
                checked_at=now,
            )
        except Exception as e:
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.FAIL,
                message=f"Broker health check failed: {e}",
                checked_at=now,
            )
