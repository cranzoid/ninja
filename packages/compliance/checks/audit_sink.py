"""AuditSinkCheck — verifies audit ledger is writable and readable."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from packages.contracts.audit_event import AuditEvent
from packages.contracts.compliance import (
    ComplianceContext,
    ComplianceResult,
    ComplianceStatus,
)
from services.audit_ledger.ledger import AuditLedger


class AuditSinkCheck:
    """Writes a test AuditEvent to the ledger and reads it back."""

    name: str = "audit_sink"
    description: str = "Audit ledger is writable and readable"
    blocking: bool = True

    def __init__(self, audit_ledger: AuditLedger) -> None:
        self._ledger = audit_ledger

    async def run(self, context: ComplianceContext) -> ComplianceResult:
        now = datetime.now(UTC)
        test_event_id = f"compliance_check_{uuid.uuid4()}"

        try:
            # Write a test event
            test_event = AuditEvent(
                event_id=test_event_id,
                timestamp=now,
                event_type="compliance_audit_sink_test",
                source_service="compliance_gate",
                mode=context.mode,
                payload={"test": True, "purpose": "audit_sink_check"},
                operator_visible=False,
            )
            await self._ledger.record(test_event)

            # Read it back
            events = await self._ledger.get_events_for_date(now.date())
            found = any(e.event_id == test_event_id for e in events)

            if not found:
                return ComplianceResult(
                    check_name=self.name,
                    status=ComplianceStatus.FAIL,
                    message="Audit ledger write succeeded but read-back failed.",
                    checked_at=now,
                )

            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.PASS,
                message="Audit ledger write and read-back successful.",
                checked_at=now,
            )
        except Exception as e:
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.FAIL,
                message=f"Audit sink check failed: {e}",
                checked_at=now,
            )
