"""Phase 5 tests — TradeCardGenerator."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio

from packages.contracts.candidates import SwingCandidate
from packages.contracts.enums import RegimeClass
from packages.contracts.llm import (
    LLMResponse,
    ModelRole,
    ModelRouterConfig,
    ProviderConfig,
    ProviderHealth,
    RoleRouting,
)
from packages.contracts.portfolio import PortfolioState
from packages.contracts.regime_state import RegimeState
from packages.contracts.trade_card import TradeCard
from packages.model_router.parser import StructuredOutputParser
from packages.model_router.providers.base import ProviderError
from packages.model_router.providers.fixture import FixtureProvider
from packages.model_router.router import ModelRouter
from packages.model_router.telemetry import ModelTelemetry
from packages.model_router.trade_card_generator import (
    TradeCardGenerationError,
    TradeCardGenerator,
)
from services.audit_ledger.ledger import AuditLedger


class _BadOutputProvider:
    async def complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        return LLMResponse(
            text="invalid output",
            model_name="bad",
            input_tokens=10,
            output_tokens=5,
            latency_ms=1,
            provider_name="bad",
        )

    async def health_check(self) -> ProviderHealth:
        from datetime import UTC, datetime

        return ProviderHealth(
            is_healthy=True, latency_ms=1, last_checked=datetime.now(UTC)
        )


class _FailingProvider:
    async def complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        raise ProviderError("failing", RuntimeError("down"))

    async def health_check(self) -> ProviderHealth:
        from datetime import UTC, datetime

        return ProviderHealth(
            is_healthy=False,
            latency_ms=0,
            last_checked=datetime.now(UTC),
            error_message="down",
        )


def _swing_candidate() -> SwingCandidate:
    return SwingCandidate(
        symbol="RELIANCE",
        scan_date=date(2026, 3, 26),
        close=Decimal("2840.00"),
        entry_price_estimate=Decimal("2850.00"),
        stop_price=Decimal("2780.00"),
        risk_per_share=Decimal("70.00"),
        volume_ratio=Decimal("1.45"),
        atr_14=Decimal("45.00"),
        regime_at_scan=RegimeClass.GREEN,
        passes_all_entry_conditions=True,
        failed_conditions=[],
    )


def _regime() -> RegimeState:
    return RegimeState(
        assessed_at=datetime.now(UTC),
        regime_class=RegimeClass.GREEN,
        nifty50_trend="bullish",
        breadth_above_50dma_pct=Decimal("72.0"),
        breadth_above_200dma_pct=Decimal("80.0"),
        vix_level=Decimal("14.0"),
        vix_state="low",
        gap_frequency_5d=Decimal("1.0"),
        sector_concentration_score=Decimal("0.3"),
        correlation_state="normal",
        sizing_multiplier=Decimal("1.0"),
        rationale="Broad strength, low VIX.",
    )


def _portfolio() -> PortfolioState:
    return PortfolioState(
        equity=Decimal("500000"),
        cash=Decimal("400000"),
        positions=[],
        open_risk_pct=Decimal("1.0"),
        sector_exposure={},
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


@pytest_asyncio.fixture
async def audit_ledger(tmp_path: Path) -> AuditLedger:
    return AuditLedger(tmp_path / "audit")


class TestTradeCardGeneratorSuccess:
    async def test_generate_returns_trade_card(
        self, audit_ledger: AuditLedger
    ) -> None:
        telemetry = ModelTelemetry()
        router = ModelRouter(
            config=_fixture_config(),
            providers={"fixture": FixtureProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        gen = TradeCardGenerator(
            router=router,
            parser=StructuredOutputParser(),
            audit_ledger=audit_ledger,
        )
        card = await gen.generate(_swing_candidate(), _regime(), _portfolio())
        assert isinstance(card, TradeCard)
        assert card.symbol == "RELIANCE"
        assert card.layer.value == "swing"

    async def test_trade_card_has_valid_risk(
        self, audit_ledger: AuditLedger
    ) -> None:
        telemetry = ModelTelemetry()
        router = ModelRouter(
            config=_fixture_config(),
            providers={"fixture": FixtureProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        gen = TradeCardGenerator(
            router=router,
            parser=StructuredOutputParser(),
            audit_ledger=audit_ledger,
        )
        card = await gen.generate(_swing_candidate(), _regime(), _portfolio())
        assert card.risk_per_share == card.entry_price_target - card.stop_price


class TestTradeCardGeneratorFailure:
    async def test_parse_error_raises_generation_error(
        self, audit_ledger: AuditLedger
    ) -> None:
        config = ModelRouterConfig(
            providers={"bad": ProviderConfig(name="bad", model_name="v1")},
            role_routing={
                ModelRole.BLOCKER_SCAN: RoleRouting(primary="bad"),
                ModelRole.TRADE_CARD: RoleRouting(primary="bad"),
                ModelRole.EXPLANATION: RoleRouting(primary="bad"),
            },
        )
        telemetry = ModelTelemetry()
        router = ModelRouter(
            config=config,
            providers={"bad": _BadOutputProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        gen = TradeCardGenerator(
            router=router,
            parser=StructuredOutputParser(),
            audit_ledger=audit_ledger,
        )
        with pytest.raises(TradeCardGenerationError):
            await gen.generate(_swing_candidate(), _regime(), _portfolio())

    async def test_provider_failure_raises_generation_error(
        self, audit_ledger: AuditLedger
    ) -> None:
        config = ModelRouterConfig(
            providers={
                "failing": ProviderConfig(name="failing", model_name="v1")
            },
            role_routing={
                ModelRole.BLOCKER_SCAN: RoleRouting(primary="failing"),
                ModelRole.TRADE_CARD: RoleRouting(primary="failing"),
                ModelRole.EXPLANATION: RoleRouting(primary="failing"),
            },
        )
        telemetry = ModelTelemetry()
        router = ModelRouter(
            config=config,
            providers={"failing": _FailingProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        gen = TradeCardGenerator(
            router=router,
            parser=StructuredOutputParser(),
            audit_ledger=audit_ledger,
        )
        with pytest.raises(TradeCardGenerationError):
            await gen.generate(_swing_candidate(), _regime(), _portfolio())

    async def test_failure_logs_audit_event(
        self, audit_ledger: AuditLedger
    ) -> None:
        config = ModelRouterConfig(
            providers={"bad": ProviderConfig(name="bad", model_name="v1")},
            role_routing={
                ModelRole.BLOCKER_SCAN: RoleRouting(primary="bad"),
                ModelRole.TRADE_CARD: RoleRouting(primary="bad"),
                ModelRole.EXPLANATION: RoleRouting(primary="bad"),
            },
        )
        telemetry = ModelTelemetry()
        router = ModelRouter(
            config=config,
            providers={"bad": _BadOutputProvider()},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
        )
        gen = TradeCardGenerator(
            router=router,
            parser=StructuredOutputParser(),
            audit_ledger=audit_ledger,
        )
        with pytest.raises(TradeCardGenerationError):
            await gen.generate(_swing_candidate(), _regime(), _portfolio())

        from datetime import UTC, datetime

        events = await audit_ledger.get_events_for_date(
            datetime.now(UTC).date()
        )
        failure_events = [
            e
            for e in events
            if e.event_type == "trade_card_generation_failure"
        ]
        assert len(failure_events) >= 1
        assert failure_events[0].related_symbol == "RELIANCE"
