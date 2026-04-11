"""Tests for the 8-fix patch — verifies correct wiring in shadow/live mode.

Covers:
- Fix 1: Compliance broker checks use ZerodhaAdapter in shadow-live mode
- Fix 2: active_broker property returns the right adapter per mode
- Fix 6: ModelRouter always includes BedrockProvider in non-paper mode
- Fix 7: ShadowLiveRunner uses real LLMBlockerProvider (not StubBlockerProvider)
- Fix 8: ShadowLiveRunner uses YFinanceMarketDataProvider in shadow-live mode
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio

from apps.api.src.services.app_state import AppState, make_default_config
from packages.brokers.mock_broker import MockBrokerAdapter
from packages.brokers.zerodha import ZerodhaAdapter
from packages.compliance.checks.broker_auth import BrokerAuthCheck
from packages.compliance.checks.broker_health import BrokerHealthCheck
from packages.contracts.enums import Mode
from packages.model_router.blocker_provider import LLMBlockerProvider
from packages.model_router.providers.bedrock import BedrockProvider
from services.data_ingest.providers.fixture_provider import FixtureMarketDataProvider
from services.data_ingest.providers.yfinance_provider import YFinanceMarketDataProvider
from services.paper_broker.stub_blocker import StubBlockerProvider


@pytest_asyncio.fixture
async def paper_state(tmp_path: Path) -> AppState:
    """AppState initialized in paper mode."""
    cfg = make_default_config(mode=Mode.PAPER)
    return await AppState.initialize(tmp_path, cfg)


@pytest_asyncio.fixture
async def shadow_state(tmp_path: Path) -> AppState:
    """AppState initialized in shadow-live mode."""
    os.environ["MODE"] = "shadow-live"
    cfg = make_default_config(mode=Mode.SHADOW_LIVE)
    state = await AppState.initialize(tmp_path, cfg)
    return state


# ── Fix 1: Compliance broker checks use ZerodhaAdapter in shadow/live ─────────

class TestComplianceBrokerWiring:
    @pytest.mark.asyncio
    async def test_broker_auth_check_uses_zerodha_in_shadow_live(
        self, shadow_state: AppState
    ) -> None:
        """Fix 1: BrokerAuthCheck is wired to ZerodhaAdapter in shadow-live mode."""
        assert shadow_state.compliance_gate is not None
        raw = next(
            c for c in shadow_state.compliance_gate._checks
            if getattr(c, "name", "") == "broker_auth"
        )
        assert isinstance(raw, BrokerAuthCheck)
        assert isinstance(raw._broker, ZerodhaAdapter), (
            "BrokerAuthCheck must use ZerodhaAdapter in shadow-live, not mock"
        )

    @pytest.mark.asyncio
    async def test_broker_health_check_uses_zerodha_in_shadow_live(
        self, shadow_state: AppState
    ) -> None:
        """Fix 1: BrokerHealthCheck is wired to ZerodhaAdapter in shadow-live mode."""
        assert shadow_state.compliance_gate is not None
        raw = next(
            c for c in shadow_state.compliance_gate._checks
            if getattr(c, "name", "") == "broker_health"
        )
        assert isinstance(raw, BrokerHealthCheck)
        assert isinstance(raw._broker, ZerodhaAdapter), (
            "BrokerHealthCheck must use ZerodhaAdapter in shadow-live, not mock"
        )

    @pytest.mark.asyncio
    async def test_broker_auth_check_uses_mock_in_paper_mode(
        self, paper_state: AppState
    ) -> None:
        """Fix 1: BrokerAuthCheck uses MockBrokerAdapter in paper mode (unchanged)."""
        assert paper_state.compliance_gate is not None
        raw = next(
            c for c in paper_state.compliance_gate._checks
            if getattr(c, "name", "") == "broker_auth"
        )
        assert isinstance(raw, BrokerAuthCheck)
        assert isinstance(raw._broker, MockBrokerAdapter), (
            "BrokerAuthCheck must use MockBrokerAdapter in paper mode"
        )


# ── Fix 2: active_broker returns correct adapter per mode ──────────────────────

class TestActiveBroker:
    @pytest.mark.asyncio
    async def test_active_broker_is_zerodha_in_shadow_live(
        self, shadow_state: AppState
    ) -> None:
        """Fix 2: active_broker returns ZerodhaAdapter in shadow-live mode."""
        assert isinstance(shadow_state.active_broker, ZerodhaAdapter), (
            "active_broker must return ZerodhaAdapter in shadow-live mode"
        )

    @pytest.mark.asyncio
    async def test_active_broker_is_mock_in_paper_mode(
        self, paper_state: AppState
    ) -> None:
        """Fix 2: active_broker returns MockBrokerAdapter in paper mode."""
        assert isinstance(paper_state.active_broker, MockBrokerAdapter), (
            "active_broker must return MockBrokerAdapter in paper mode"
        )

    @pytest.mark.asyncio
    async def test_active_broker_not_none_in_both_modes(
        self, paper_state: AppState, shadow_state: AppState
    ) -> None:
        """Fix 2: active_broker is always non-None in both modes."""
        assert paper_state.active_broker is not None
        assert shadow_state.active_broker is not None


# ── Fix 6: BedrockProvider always registered in non-paper mode ────────────────

class TestBedrockProviderWiring:
    @pytest.mark.asyncio
    async def test_bedrock_in_model_router_providers_for_shadow_live(
        self, shadow_state: AppState
    ) -> None:
        """Fix 6: BedrockProvider is registered in model_router for shadow-live mode."""
        providers = shadow_state.model_router._providers
        assert "bedrock" in providers, (
            "BedrockProvider must be registered in model_router in shadow-live mode"
        )
        assert isinstance(providers["bedrock"], BedrockProvider)

    @pytest.mark.asyncio
    async def test_bedrock_not_in_model_router_for_paper_mode(
        self, paper_state: AppState
    ) -> None:
        """Fix 6: BedrockProvider is NOT registered in paper mode (fixture only)."""
        providers = paper_state.model_router._providers
        assert "bedrock" not in providers
        assert "fixture" in providers

    @pytest.mark.asyncio
    async def test_bedrock_uses_inference_profile_model_id(
        self, shadow_state: AppState
    ) -> None:
        """Fix 5+6: BedrockProvider uses inference profile ID, not raw model ID."""
        bedrock_provider = shadow_state.model_router._providers["bedrock"]
        assert isinstance(bedrock_provider, BedrockProvider)
        model_id = bedrock_provider._model_id
        # Inference profile IDs start with "global." — raw IDs start with "anthropic."
        assert model_id.startswith("global."), (
            f"BedrockProvider must use inference profile ID (global.*), got: {model_id}"
        )


# ── Fix 7: ShadowLiveRunner uses real LLMBlockerProvider ──────────────────────

class TestShadowRunnerBlockerWiring:
    @pytest.mark.asyncio
    async def test_shadow_runner_uses_real_blocker_in_shadow_live(
        self, shadow_state: AppState
    ) -> None:
        """Fix 7: shadow_runner._blocker_provider is real LLMBlockerProvider."""
        assert shadow_state.shadow_runner is not None
        blocker = shadow_state.shadow_runner._blocker_provider
        assert isinstance(blocker, LLMBlockerProvider), (
            "shadow_runner must use LLMBlockerProvider, not StubBlockerProvider"
        )
        assert not isinstance(blocker, StubBlockerProvider)

    @pytest.mark.asyncio
    async def test_shadow_runner_blocker_is_same_as_appstate_blocker(
        self, shadow_state: AppState
    ) -> None:
        """Fix 7: shadow_runner uses the same blocker_provider as AppState."""
        assert shadow_state.shadow_runner is not None
        assert (
            shadow_state.shadow_runner._blocker_provider
            is shadow_state.blocker_provider
        )

    def test_shadow_runner_falls_back_to_stub_when_none_passed(
        self,
        tmp_path: Path,
    ) -> None:
        """Fix 7: ShadowLiveRunner falls back to StubBlockerProvider if none given."""
        from packages.brokers.mock_broker import MockBrokerAdapter
        from packages.brokers.shadow_runner import ShadowLiveRunner
        from packages.contracts.broker import BrokerConfig
        from services.audit_ledger.ledger import AuditLedger

        ledger = AuditLedger(tmp_path / "audit")
        cfg = BrokerConfig(
            broker_name="mock", base_url="http://localhost", dry_run=True
        )
        broker = MockBrokerAdapter(config=cfg, audit_ledger=ledger)
        runner = ShadowLiveRunner(
            data_provider=FixtureMarketDataProvider(),
            mock_broker=broker,
            audit_ledger=ledger,
            blocker_provider=None,
        )
        assert isinstance(runner._blocker_provider, StubBlockerProvider)


# ── Fix 8: ShadowLiveRunner uses YFinanceMarketDataProvider in shadow-live ────

class TestShadowRunnerDataProviderWiring:
    @pytest.mark.asyncio
    async def test_shadow_runner_uses_yfinance_in_shadow_live(
        self, shadow_state: AppState
    ) -> None:
        """Fix 8: shadow_runner uses YFinanceMarketDataProvider in shadow-live mode."""
        assert shadow_state.shadow_runner is not None
        assert isinstance(
            shadow_state.shadow_runner._data_provider, YFinanceMarketDataProvider
        ), (
            "shadow_runner must use YFinanceMarketDataProvider in shadow-live mode, "
            "not FixtureMarketDataProvider"
        )

    @pytest.mark.asyncio
    async def test_shadow_runner_uses_fixture_in_paper_mode(
        self, paper_state: AppState
    ) -> None:
        """Fix 8: shadow_runner uses FixtureMarketDataProvider in paper mode."""
        assert paper_state.shadow_runner is not None
        assert isinstance(
            paper_state.shadow_runner._data_provider, FixtureMarketDataProvider
        ), (
            "shadow_runner must use FixtureMarketDataProvider in paper mode"
        )
