"""Phase 5 tests — ModelRouter with fallback logic."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from packages.contracts.llm import (
    LLMResponse,
    ModelRole,
    ModelRouterConfig,
    ProviderConfig,
    ProviderHealth,
    RoleRouting,
)
from packages.model_router.providers.base import (
    AllProvidersFailedError,
    ProviderError,
)
from packages.model_router.providers.fixture import FixtureProvider
from packages.model_router.router import ModelRouter
from packages.model_router.telemetry import ModelTelemetry
from services.audit_ledger.ledger import AuditLedger


class _FailingProvider:
    """Provider that always fails."""

    def __init__(self, name: str = "failing") -> None:
        self._name = name

    async def complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        raise ProviderError(self._name, RuntimeError("Simulated failure"))

    async def health_check(self) -> ProviderHealth:
        from datetime import UTC, datetime

        return ProviderHealth(
            is_healthy=False,
            latency_ms=0,
            last_checked=datetime.now(UTC),
            error_message="Simulated failure",
        )


def _make_config(
    primary: str = "fixture",
    fallback: str | None = None,
) -> ModelRouterConfig:
    providers: dict[str, ProviderConfig] = {
        "fixture": ProviderConfig(name="fixture", model_name="fixture-v1"),
    }
    if fallback == "fixture_backup":
        providers["fixture_backup"] = ProviderConfig(
            name="fixture_backup", model_name="fixture-v1"
        )
    if "failing" not in providers and (
        primary == "failing" or fallback == "failing"
    ):
        providers["failing"] = ProviderConfig(
            name="failing", model_name="failing-v1"
        )

    role_routing = {
        ModelRole.BLOCKER_SCAN: RoleRouting(primary=primary, fallback=fallback),
        ModelRole.TRADE_CARD: RoleRouting(primary=primary, fallback=fallback),
        ModelRole.EXPLANATION: RoleRouting(primary=primary, fallback=fallback),
    }
    return ModelRouterConfig(providers=providers, role_routing=role_routing)


@pytest_asyncio.fixture
async def audit_ledger(tmp_path: Path) -> AuditLedger:
    return AuditLedger(tmp_path / "audit")


@pytest_asyncio.fixture
async def telemetry() -> ModelTelemetry:
    return ModelTelemetry()


class TestModelRouterPrimarySuccess:
    async def test_primary_success_returns_response(
        self, audit_ledger: AuditLedger, telemetry: ModelTelemetry
    ) -> None:
        config = _make_config(primary="fixture")
        router = ModelRouter(
            config=config,
            providers={"fixture": FixtureProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        response = await router.complete(
            role=ModelRole.BLOCKER_SCAN,
            prompt="Symbol: RELIANCE\nTest prompt",
            system="blocker scan system prompt",
        )
        assert isinstance(response, LLMResponse)
        assert response.provider_name == "fixture"
        assert len(response.text) > 0

    async def test_primary_success_correct_model(
        self, audit_ledger: AuditLedger, telemetry: ModelTelemetry
    ) -> None:
        config = _make_config(primary="fixture")
        router = ModelRouter(
            config=config,
            providers={"fixture": FixtureProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        response = await router.complete(
            role=ModelRole.TRADE_CARD,
            prompt="test",
            system="trade card thesis extractor",
        )
        assert response.model_name == "fixture-model-v1"


class TestModelRouterFallback:
    async def test_fallback_on_primary_failure(
        self, audit_ledger: AuditLedger, telemetry: ModelTelemetry
    ) -> None:
        config = _make_config(primary="failing", fallback="fixture")
        router = ModelRouter(
            config=config,
            providers={
                "failing": _FailingProvider("failing"),
                "fixture": FixtureProvider(),
            },
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        response = await router.complete(
            role=ModelRole.BLOCKER_SCAN,
            prompt="Symbol: RELIANCE\nTest",
            system="blocker scan",
        )
        assert response.provider_name == "fixture"

    async def test_fallback_telemetry_recorded(
        self, audit_ledger: AuditLedger, telemetry: ModelTelemetry
    ) -> None:
        config = _make_config(primary="failing", fallback="fixture")
        router = ModelRouter(
            config=config,
            providers={
                "failing": _FailingProvider("failing"),
                "fixture": FixtureProvider(),
            },
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        await router.complete(
            role=ModelRole.BLOCKER_SCAN,
            prompt="Symbol: RELIANCE\nTest",
            system="blocker scan",
        )
        summary = telemetry.get_summary()
        # Records for failing (failure) + fixture (fallback success)
        assert summary.total_calls >= 2


class TestModelRouterBothFail:
    async def test_both_fail_raises_error(
        self, audit_ledger: AuditLedger, telemetry: ModelTelemetry
    ) -> None:
        config = _make_config(primary="failing", fallback="failing")
        config = ModelRouterConfig(
            providers={
                "failing": ProviderConfig(name="failing", model_name="fail-v1"),
                "failing2": ProviderConfig(
                    name="failing2", model_name="fail-v1"
                ),
            },
            role_routing={
                ModelRole.BLOCKER_SCAN: RoleRouting(
                    primary="failing", fallback="failing2"
                ),
                ModelRole.TRADE_CARD: RoleRouting(primary="failing"),
                ModelRole.EXPLANATION: RoleRouting(primary="failing"),
            },
        )
        router = ModelRouter(
            config=config,
            providers={
                "failing": _FailingProvider("failing"),
                "failing2": _FailingProvider("failing2"),
            },
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        with pytest.raises(AllProvidersFailedError):
            await router.complete(
                role=ModelRole.BLOCKER_SCAN,
                prompt="Test",
                system="blocker",
            )

    async def test_both_fail_error_contains_providers(
        self, audit_ledger: AuditLedger, telemetry: ModelTelemetry
    ) -> None:
        config = ModelRouterConfig(
            providers={
                "p1": ProviderConfig(name="p1", model_name="v1"),
                "p2": ProviderConfig(name="p2", model_name="v1"),
            },
            role_routing={
                ModelRole.BLOCKER_SCAN: RoleRouting(
                    primary="p1", fallback="p2"
                ),
                ModelRole.TRADE_CARD: RoleRouting(primary="p1"),
                ModelRole.EXPLANATION: RoleRouting(primary="p1"),
            },
        )
        router = ModelRouter(
            config=config,
            providers={
                "p1": _FailingProvider("p1"),
                "p2": _FailingProvider("p2"),
            },
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        with pytest.raises(AllProvidersFailedError) as exc_info:
            await router.complete(
                role=ModelRole.BLOCKER_SCAN,
                prompt="Test",
                system="blocker",
            )
        assert len(exc_info.value.errors) == 2


class TestModelRouterAudit:
    async def test_routing_decision_logged(
        self, audit_ledger: AuditLedger, telemetry: ModelTelemetry
    ) -> None:
        config = _make_config(primary="fixture")
        router = ModelRouter(
            config=config,
            providers={"fixture": FixtureProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        await router.complete(
            role=ModelRole.BLOCKER_SCAN,
            prompt="Symbol: RELIANCE\nTest",
            system="blocker scan",
        )
        from datetime import UTC, datetime

        events = await audit_ledger.get_events_for_date(
            datetime.now(UTC).date()
        )
        routing_events = [
            e for e in events if e.event_type == "model_routing_decision"
        ]
        assert len(routing_events) >= 1
        assert routing_events[0].payload["role"] == "blocker_scan"

    async def test_all_providers_failed_logged(
        self, audit_ledger: AuditLedger, telemetry: ModelTelemetry
    ) -> None:
        config = ModelRouterConfig(
            providers={
                "p1": ProviderConfig(name="p1", model_name="v1"),
            },
            role_routing={
                ModelRole.BLOCKER_SCAN: RoleRouting(primary="p1"),
                ModelRole.TRADE_CARD: RoleRouting(primary="p1"),
                ModelRole.EXPLANATION: RoleRouting(primary="p1"),
            },
        )
        router = ModelRouter(
            config=config,
            providers={"p1": _FailingProvider("p1")},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        with pytest.raises(AllProvidersFailedError):
            await router.complete(
                role=ModelRole.BLOCKER_SCAN,
                prompt="Test",
                system="blocker",
            )
        from datetime import UTC, datetime

        events = await audit_ledger.get_events_for_date(
            datetime.now(UTC).date()
        )
        failed_events = [
            e for e in events if e.event_type == "all_providers_failed"
        ]
        assert len(failed_events) >= 1


class TestModelRouterHealthCheck:
    async def test_health_check_all(
        self, audit_ledger: AuditLedger, telemetry: ModelTelemetry
    ) -> None:
        config = _make_config(primary="fixture")
        router = ModelRouter(
            config=config,
            providers={"fixture": FixtureProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        results = await router.health_check_all()
        assert "fixture" in results
        assert results["fixture"].is_healthy is True

    async def test_health_check_failing_provider(
        self, audit_ledger: AuditLedger, telemetry: ModelTelemetry
    ) -> None:
        config = _make_config(primary="failing")
        router = ModelRouter(
            config=config,
            providers={"failing": _FailingProvider("failing")},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        results = await router.health_check_all()
        assert "failing" in results
        assert results["failing"].is_healthy is False
