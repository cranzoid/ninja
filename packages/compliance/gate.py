"""ComplianceGate — runs all compliance checks and determines live readiness.

Phase 6: Pre-live compliance gate per charter section 9.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from packages.compliance.checks.base import ComplianceCheck
from packages.contracts.audit_event import AuditEvent
from packages.contracts.compliance import (
    ComplianceContext,
    ComplianceReport,
    ComplianceResult,
    ComplianceStatus,
)
from services.audit_ledger.ledger import AuditLedger

logger = logging.getLogger(__name__)


class ComplianceGate:
    """Runs all compliance checks and produces a ComplianceReport.

    Logic:
    - run_all() runs all checks concurrently (asyncio.gather), collects results
    - can_arm_live() returns True only if all blocking checks PASS
    - Every check result logged as AuditEvent regardless of pass/fail
    - On any check raising an unexpected exception: treated as FAIL, gate does not crash
    """

    def __init__(
        self,
        checks: list[ComplianceCheck],
        audit_ledger: AuditLedger,
        mode: str = "paper",
    ) -> None:
        self._checks = checks
        self._ledger = audit_ledger
        self._mode = mode

    async def _run_single_check(
        self, check: ComplianceCheck, context: ComplianceContext
    ) -> ComplianceResult:
        """Run a single check, catching unexpected exceptions."""
        try:
            run_fn = check.run
            result: ComplianceResult = await run_fn(context)
            return result
        except Exception as e:
            logger.exception(
                "Compliance check %s raised unexpected exception",
                getattr(check, "name", "unknown"),
            )
            return ComplianceResult(
                check_name=getattr(check, "name", "unknown"),
                status=ComplianceStatus.FAIL,
                message=f"Check raised exception: {e}",
                checked_at=datetime.now(UTC),
            )

    async def run_all(self, context: ComplianceContext) -> ComplianceReport:
        """Run all compliance checks concurrently and return a report."""
        tasks = [self._run_single_check(check, context) for check in self._checks]
        results = await asyncio.gather(*tasks)

        # Log each result as an audit event
        for result in results:
            await self._log_result(result, context)

        # Determine if all blocking checks passed
        all_blocking_passed = True
        for check, result in zip(self._checks, results, strict=True):
            is_blocking = getattr(check, "blocking", True)
            if is_blocking and result.status == ComplianceStatus.FAIL:
                all_blocking_passed = False

        return ComplianceReport(
            results=list(results),
            all_blocking_passed=all_blocking_passed,
            generated_at=datetime.now(UTC),
            mode=context.mode,
        )

    async def can_arm_live(self, context: ComplianceContext) -> bool:
        """Return True only if all blocking checks PASS."""
        report = await self.run_all(context)
        return report.all_blocking_passed

    async def _log_result(
        self, result: ComplianceResult, context: ComplianceContext
    ) -> None:
        """Log a compliance check result as an AuditEvent."""
        try:
            event = AuditEvent(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC),
                event_type="compliance_check",
                source_service="compliance_gate",
                mode=context.mode,
                payload={
                    "check_name": result.check_name,
                    "status": result.status.value,
                    "message": result.message,
                },
                operator_visible=result.status == ComplianceStatus.FAIL,
            )
            await self._ledger.record(event)
        except Exception:
            logger.exception("Failed to log compliance check result")
