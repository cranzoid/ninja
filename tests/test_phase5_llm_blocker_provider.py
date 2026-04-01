"""Phase 5 tests — LLMBlockerProvider."""

from __future__ import annotations

from pathlib import Path

import pytest_asyncio

from packages.contracts.blocker_report import BlockerReport
from packages.contracts.llm import (
    LLMResponse,
    ModelRole,
    ModelRouterConfig,
    ProviderConfig,
    ProviderHealth,
    RoleRouting,
)
from packages.model_router.blocker_provider import LLMBlockerProvider
from packages.model_router.parser import StructuredOutputParser
from packages.model_router.providers.base import (
    ProviderError,
)
from packages.model_router.providers.fixture import FixtureProvider
from packages.model_router.router import ModelRouter
from packages.model_router.telemetry import ModelTelemetry
from services.audit_ledger.ledger import AuditLedger


class _BadOutputProvider:
    """Provider that returns invalid JSON."""

    async def complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        return LLMResponse(
            text="this is not json",
            model_name="bad-model",
            input_tokens=10,
            output_tokens=5,
            latency_ms=1,
            provider_name="bad",
        )

    async def health_check(self) -> ProviderHealth:
        from datetime import UTC, datetime

        return ProviderHealth(
            is_healthy=True,
            latency_ms=1,
            last_checked=datetime.now(UTC),
        )


class _FailingProvider:
    """Provider that always fails."""

    async def complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        raise ProviderError("failing", RuntimeError("Simulated failure"))

    async def health_check(self) -> ProviderHealth:
        from datetime import UTC, datetime

        return ProviderHealth(
            is_healthy=False,
            latency_ms=0,
            last_checked=datetime.now(UTC),
            error_message="down",
        )


def _fixture_config() -> ModelRouterConfig:
    return ModelRouterConfig(
        providers={"fixture": ProviderConfig(name="fixture", model_name="v1")},
        role_routing={
            ModelRole.BLOCKER_SCAN: RoleRouting(primary="fixture"),
            ModelRole.TRADE_CARD: RoleRouting(primary="fixture"),
            ModelRole.EXPLANATION: RoleRouting(primary="fixture"),
        },
    )


def _bad_config() -> ModelRouterConfig:
    return ModelRouterConfig(
        providers={"bad": ProviderConfig(name="bad", model_name="v1")},
        role_routing={
            ModelRole.BLOCKER_SCAN: RoleRouting(primary="bad"),
            ModelRole.TRADE_CARD: RoleRouting(primary="bad"),
            ModelRole.EXPLANATION: RoleRouting(primary="bad"),
        },
    )


def _failing_config() -> ModelRouterConfig:
    return ModelRouterConfig(
        providers={"failing": ProviderConfig(name="failing", model_name="v1")},
        role_routing={
            ModelRole.BLOCKER_SCAN: RoleRouting(primary="failing"),
            ModelRole.TRADE_CARD: RoleRouting(primary="failing"),
            ModelRole.EXPLANATION: RoleRouting(primary="failing"),
        },
    )


@pytest_asyncio.fixture
async def audit_ledger(tmp_path: Path) -> AuditLedger:
    return AuditLedger(tmp_path / "audit")


class TestLLMBlockerProviderSuccess:
    async def test_successful_scan(self, audit_ledger: AuditLedger) -> None:
        telemetry = ModelTelemetry()
        router = ModelRouter(
            config=_fixture_config(),
            providers={"fixture": FixtureProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        provider = LLMBlockerProvider(
            router=router,
            parser=StructuredOutputParser(),
            audit_ledger=audit_ledger,
        )
        report = await provider.get_blocker_report(
            symbol="RELIANCE",
            headlines=["Test headline"],
            price=2850.0,
            atr=45.0,
        )
        assert isinstance(report, BlockerReport)
        assert report.symbol == "RELIANCE"
        assert report.is_blocked is False

    async def test_blocker_detected(self, audit_ledger: AuditLedger) -> None:
        telemetry = ModelTelemetry()
        router = ModelRouter(
            config=_fixture_config(),
            providers={"fixture": FixtureProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        provider = LLMBlockerProvider(
            router=router,
            parser=StructuredOutputParser(),
            audit_ledger=audit_ledger,
        )
        # HDFCBANK triggers the fixture's canned blocker response
        report = await provider.get_blocker_report(
            symbol="HDFCBANK",
            headlines=["HDFC Bank Q4 results expected"],
            price=1650.0,
            atr=30.0,
        )
        assert isinstance(report, BlockerReport)
        assert report.symbol == "HDFCBANK"
        assert report.is_blocked is True

    async def test_scan_blockers_compat(
        self, audit_ledger: AuditLedger
    ) -> None:
        """Test scan_blockers() compatibility with StubBlockerProvider."""
        telemetry = ModelTelemetry()
        router = ModelRouter(
            config=_fixture_config(),
            providers={"fixture": FixtureProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        provider = LLMBlockerProvider(
            router=router,
            parser=StructuredOutputParser(),
            audit_ledger=audit_ledger,
        )
        report = await provider.scan_blockers("RELIANCE")
        assert isinstance(report, BlockerReport)

    async def test_deterministic_fixture_responses(
        self, audit_ledger: AuditLedger
    ) -> None:
        """Fixture provider returns same result for same input."""
        telemetry = ModelTelemetry()
        router = ModelRouter(
            config=_fixture_config(),
            providers={"fixture": FixtureProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        provider = LLMBlockerProvider(
            router=router,
            parser=StructuredOutputParser(),
            audit_ledger=audit_ledger,
        )
        r1 = await provider.get_blocker_report("RELIANCE", [], 100.0, 5.0)
        r2 = await provider.get_blocker_report("RELIANCE", [], 100.0, 5.0)
        assert r1.is_blocked == r2.is_blocked
        assert r1.symbol == r2.symbol


class TestLLMBlockerProviderParseFailure:
    async def test_parse_error_returns_safe_default(
        self, audit_ledger: AuditLedger
    ) -> None:
        telemetry = ModelTelemetry()
        router = ModelRouter(
            config=_bad_config(),
            providers={"bad": _BadOutputProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        provider = LLMBlockerProvider(
            router=router,
            parser=StructuredOutputParser(),
            audit_ledger=audit_ledger,
        )
        report = await provider.get_blocker_report(
            symbol="RELIANCE",
            headlines=[],
            price=100.0,
            atr=5.0,
        )
        assert isinstance(report, BlockerReport)
        # Safe default — doesn't block (is_blocked=False since no blockers_found)
        assert report.model_provider == "safe_default"

    async def test_parse_error_audit_event(
        self, audit_ledger: AuditLedger
    ) -> None:
        telemetry = ModelTelemetry()
        router = ModelRouter(
            config=_bad_config(),
            providers={"bad": _BadOutputProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        provider = LLMBlockerProvider(
            router=router,
            parser=StructuredOutputParser(),
            audit_ledger=audit_ledger,
        )
        await provider.get_blocker_report(
            symbol="RELIANCE", headlines=[], price=100.0, atr=5.0
        )
        from datetime import UTC, datetime

        events = await audit_ledger.get_events_for_date(
            datetime.now(UTC).date()
        )
        parse_events = [
            e
            for e in events
            if e.event_type == "blocker_scan_parse_failure"
        ]
        assert len(parse_events) >= 1


class TestLLMBlockerProviderProviderFailure:
    async def test_provider_failure_returns_safe_default(
        self, audit_ledger: AuditLedger
    ) -> None:
        telemetry = ModelTelemetry()
        router = ModelRouter(
            config=_failing_config(),
            providers={"failing": _FailingProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        provider = LLMBlockerProvider(
            router=router,
            parser=StructuredOutputParser(),
            audit_ledger=audit_ledger,
        )
        report = await provider.get_blocker_report(
            symbol="RELIANCE", headlines=[], price=100.0, atr=5.0
        )
        assert isinstance(report, BlockerReport)
        assert report.model_provider == "safe_default"

    async def test_provider_failure_audit_event(
        self, audit_ledger: AuditLedger
    ) -> None:
        telemetry = ModelTelemetry()
        router = ModelRouter(
            config=_failing_config(),
            providers={"failing": _FailingProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        provider = LLMBlockerProvider(
            router=router,
            parser=StructuredOutputParser(),
            audit_ledger=audit_ledger,
        )
        await provider.get_blocker_report(
            symbol="TCS", headlines=[], price=100.0, atr=5.0
        )
        from datetime import UTC, datetime

        events = await audit_ledger.get_events_for_date(
            datetime.now(UTC).date()
        )
        provider_events = [
            e
            for e in events
            if e.event_type == "blocker_scan_provider_failure"
        ]
        assert len(provider_events) >= 1
