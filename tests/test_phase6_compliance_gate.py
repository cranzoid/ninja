"""Phase 6 tests — compliance gate runner (8+ tests)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio

from packages.compliance.gate import ComplianceGate
from packages.contracts.broker import BrokerConfig
from packages.contracts.compliance import (
    ComplianceContext,
    ComplianceResult,
    ComplianceStatus,
)
from packages.contracts.enums import Mode
from services.audit_ledger.ledger import AuditLedger


def _make_context(mode: Mode = Mode.PAPER) -> ComplianceContext:
    return ComplianceContext(
        mode=mode,
        broker_config=BrokerConfig(
            broker_name="mock", base_url="http://localhost", dry_run=True
        ),
        env_vars_present=[],
        armed_live=False,
    )


class _PassingCheck:
    name = "passing_check"
    description = "Always passes"
    blocking = True

    async def run(self, context: ComplianceContext) -> ComplianceResult:
        return ComplianceResult(
            check_name=self.name,
            status=ComplianceStatus.PASS,
            message="All good.",
            checked_at=datetime.now(UTC),
        )


class _FailingCheck:
    name = "failing_check"
    description = "Always fails"
    blocking = True

    async def run(self, context: ComplianceContext) -> ComplianceResult:
        return ComplianceResult(
            check_name=self.name,
            status=ComplianceStatus.FAIL,
            message="Something is wrong.",
            checked_at=datetime.now(UTC),
        )


class _WarningCheck:
    name = "warning_check"
    description = "Always warns"
    blocking = False

    async def run(self, context: ComplianceContext) -> ComplianceResult:
        return ComplianceResult(
            check_name=self.name,
            status=ComplianceStatus.WARNING,
            message="Minor issue.",
            checked_at=datetime.now(UTC),
        )


class _ExplodingCheck:
    name = "exploding_check"
    description = "Raises an exception"
    blocking = True

    async def run(self, context: ComplianceContext) -> ComplianceResult:
        raise RuntimeError("Unexpected failure in check")


class _NonBlockingFailCheck:
    name = "non_blocking_fail"
    description = "Non-blocking fail"
    blocking = False

    async def run(self, context: ComplianceContext) -> ComplianceResult:
        return ComplianceResult(
            check_name=self.name,
            status=ComplianceStatus.FAIL,
            message="Non-blocking failure.",
            checked_at=datetime.now(UTC),
        )


@pytest_asyncio.fixture
async def audit_ledger(tmp_path: Path) -> AuditLedger:
    return AuditLedger(tmp_path / "audit")


class TestComplianceGate:
    @pytest.mark.asyncio
    async def test_all_pass_can_arm_live(self, audit_ledger: AuditLedger) -> None:
        gate = ComplianceGate(
            checks=[_PassingCheck(), _PassingCheck()],
            audit_ledger=audit_ledger,
        )
        ctx = _make_context()
        result = await gate.can_arm_live(ctx)
        assert result is True

    @pytest.mark.asyncio
    async def test_blocking_fail_prevents_arm(self, audit_ledger: AuditLedger) -> None:
        gate = ComplianceGate(
            checks=[_PassingCheck(), _FailingCheck()],
            audit_ledger=audit_ledger,
        )
        ctx = _make_context()
        result = await gate.can_arm_live(ctx)
        assert result is False

    @pytest.mark.asyncio
    async def test_non_blocking_fail_still_arms(
        self, audit_ledger: AuditLedger
    ) -> None:
        gate = ComplianceGate(
            checks=[_PassingCheck(), _NonBlockingFailCheck()],
            audit_ledger=audit_ledger,
        )
        ctx = _make_context()
        result = await gate.can_arm_live(ctx)
        assert result is True

    @pytest.mark.asyncio
    async def test_exception_treated_as_fail(self, audit_ledger: AuditLedger) -> None:
        gate = ComplianceGate(
            checks=[_PassingCheck(), _ExplodingCheck()],
            audit_ledger=audit_ledger,
        )
        ctx = _make_context()
        report = await gate.run_all(ctx)
        # The exploding check should be treated as FAIL
        exploding = [r for r in report.results if r.check_name == "exploding_check"]
        assert len(exploding) == 1
        assert exploding[0].status == ComplianceStatus.FAIL
        assert "exception" in exploding[0].message.lower()

    @pytest.mark.asyncio
    async def test_exception_does_not_crash_gate(
        self, audit_ledger: AuditLedger
    ) -> None:
        gate = ComplianceGate(
            checks=[_ExplodingCheck(), _PassingCheck()],
            audit_ledger=audit_ledger,
        )
        ctx = _make_context()
        # Should not raise — gate must be resilient
        report = await gate.run_all(ctx)
        assert len(report.results) == 2

    @pytest.mark.asyncio
    async def test_all_results_logged_as_audit_events(
        self, audit_ledger: AuditLedger
    ) -> None:
        gate = ComplianceGate(
            checks=[_PassingCheck(), _FailingCheck(), _WarningCheck()],
            audit_ledger=audit_ledger,
        )
        ctx = _make_context()
        await gate.run_all(ctx)

        today_utc = datetime.now(UTC).date()
        events = await audit_ledger.get_events_for_date(today_utc)
        compliance_events = [
            e for e in events if e.event_type == "compliance_check"
        ]
        assert len(compliance_events) >= 3

    @pytest.mark.asyncio
    async def test_report_contains_all_results(self, audit_ledger: AuditLedger) -> None:
        gate = ComplianceGate(
            checks=[_PassingCheck(), _FailingCheck(), _WarningCheck()],
            audit_ledger=audit_ledger,
        )
        ctx = _make_context()
        report = await gate.run_all(ctx)
        assert len(report.results) == 3
        assert report.mode == Mode.PAPER

    @pytest.mark.asyncio
    async def test_all_blocking_passed_false_when_blocking_fails(
        self, audit_ledger: AuditLedger
    ) -> None:
        gate = ComplianceGate(
            checks=[_PassingCheck(), _FailingCheck()],
            audit_ledger=audit_ledger,
        )
        ctx = _make_context()
        report = await gate.run_all(ctx)
        assert report.all_blocking_passed is False

    @pytest.mark.asyncio
    async def test_empty_checks_list_passes(self, audit_ledger: AuditLedger) -> None:
        gate = ComplianceGate(checks=[], audit_ledger=audit_ledger)
        ctx = _make_context()
        report = await gate.run_all(ctx)
        assert report.all_blocking_passed is True
        assert len(report.results) == 0
