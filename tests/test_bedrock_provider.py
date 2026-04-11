"""Bedrock provider tests — Phase 5 model routing with AWS Bedrock."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio

# Skip all tests in this module if botocore/boto3 are not installed
pytest.importorskip("botocore")
pytest.importorskip("boto3")

from packages.contracts.enums import Mode
from packages.contracts.llm import (
    DEFAULT_ROLE_ROUTING,
    LLMResponse,
    ModelRole,
    ModelRouterConfig,
    ProviderConfig,
    ProviderHealth,
    RoleRouting,
)
from packages.model_router.providers.base import (
    LLMProvider,
    ProviderError,
)
from packages.model_router.providers.bedrock import (
    BEDROCK_MODEL_IDS,
    BedrockProvider,
)
from packages.model_router.router import ModelRouter
from packages.model_router.telemetry import ModelTelemetry
from services.audit_ledger.ledger import AuditLedger


class _FailingBedrockProvider:
    """Mock Bedrock provider that always fails."""

    async def complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        raise ProviderError(
            "bedrock",
            RuntimeError("Simulated Bedrock failure"),
        )

    async def health_check(self) -> ProviderHealth:
        from datetime import UTC, datetime

        return ProviderHealth(
            is_healthy=False,
            latency_ms=0,
            last_checked=datetime.now(UTC),
            error_message="Simulated failure",
        )


class _SuccessfulBedrockMock:
    """Mock that returns successful Bedrock response."""

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "output": {
                "message": {
                    "content": [{"text": "Mock response from Bedrock"}]
                }
            },
            "usage": {"inputTokens": 10, "outputTokens": 20},
        }


class _ClientErrorMock:
    """Mock that raises ClientError."""

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        try:
            import botocore.exceptions
            raise botocore.exceptions.ClientError(
                error_response={
                    "Error": {
                        "Code": "AccessDeniedException",
                        "Message": "Not authorized",
                    }
                },
                operation_name="Converse",
            )
        except ImportError:
            raise RuntimeError("botocore not installed") from None


class _ConnectionErrorMock:
    """Mock that raises EndpointConnectionError."""

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        try:
            import botocore.exceptions
            raise botocore.exceptions.EndpointConnectionError(
                endpoint_url="https://bedrock.ap-south-1.amazonaws.com"
            )
        except ImportError:
            raise RuntimeError("botocore not installed") from None


@pytest_asyncio.fixture
async def audit_ledger() -> AsyncGenerator[AuditLedger, None]:
    """Create a test AuditLedger."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = AuditLedger(Path(tmpdir))
        yield ledger


# --- Test 1: complete() with mocked converse response ---
@pytest.mark.asyncio
async def test_bedrock_complete_success() -> None:
    """complete() with mocked converse → returns LLMResponse with correct fields."""
    with patch("boto3.client") as mock_client_factory:
        mock_client = _SuccessfulBedrockMock()
        mock_client_factory.return_value = mock_client

        provider = BedrockProvider(
            model_id=BEDROCK_MODEL_IDS["claude-sonnet"]
        )
        response = await provider.complete(
            prompt="test prompt",
            system="test system",
            max_tokens=100,
            temperature=0.5,
        )

        assert response.text == "Mock response from Bedrock"
        assert response.model_name == BEDROCK_MODEL_IDS["claude-sonnet"]
        assert response.input_tokens == 10
        assert response.output_tokens == 20
        assert response.provider_name == "bedrock"
        assert isinstance(response.latency_ms, int)


# --- Test 2: complete() measures latency_ms > 0 ---
@pytest.mark.asyncio
async def test_bedrock_complete_latency() -> None:
    """complete() measures latency_ms > 0."""
    with patch("boto3.client") as mock_client_factory:
        mock_client = _SuccessfulBedrockMock()
        mock_client_factory.return_value = mock_client

        provider = BedrockProvider()
        response = await provider.complete(
            prompt="test",
            system="test",
            max_tokens=100,
            temperature=0.0,
        )

        assert response.latency_ms > 0


# --- Test 3: complete() ClientError → raises ProviderError ---
@pytest.mark.asyncio
async def test_bedrock_complete_client_error() -> None:
    """complete() ClientError → raises ProviderError (not ClientError)."""
    with patch("boto3.client") as mock_client_factory:
        mock_client = _ClientErrorMock()
        mock_client_factory.return_value = mock_client

        provider = BedrockProvider()
        with pytest.raises(ProviderError) as exc_info:
            await provider.complete(
                prompt="test",
                system="test",
                max_tokens=100,
                temperature=0.0,
            )

        import botocore.exceptions
        assert exc_info.value.provider_name == "bedrock"
        assert isinstance(
            exc_info.value.original_error,
            botocore.exceptions.ClientError,
        )


# --- Test 4: complete() EndpointConnectionError → raises ProviderError ---
@pytest.mark.asyncio
async def test_bedrock_complete_connection_error() -> None:
    """complete() EndpointConnectionError → raises ProviderError."""
    with patch("boto3.client") as mock_client_factory:
        mock_client = _ConnectionErrorMock()
        mock_client_factory.return_value = mock_client

        provider = BedrockProvider()
        with pytest.raises(ProviderError) as exc_info:
            await provider.complete(
                prompt="test",
                system="test",
                max_tokens=100,
                temperature=0.0,
            )

        import botocore.exceptions
        assert exc_info.value.provider_name == "bedrock"
        assert isinstance(
            exc_info.value.original_error,
            botocore.exceptions.EndpointConnectionError,
        )


# --- Test 5: health_check() success ---
@pytest.mark.asyncio
async def test_bedrock_health_check_success() -> None:
    """health_check() success → ProviderHealth(is_healthy=True, latency_ms > 0)."""
    with patch("boto3.client") as mock_client_factory:
        mock_client = _SuccessfulBedrockMock()
        mock_client_factory.return_value = mock_client

        provider = BedrockProvider()
        health = await provider.health_check()

        assert health.is_healthy is True
        assert health.latency_ms > 0
        assert health.error_message is None


# --- Test 6: health_check() on exception ---
@pytest.mark.asyncio
async def test_bedrock_health_check_failure() -> None:
    """health_check() on exception → returns unhealthy with error_message."""
    with patch("boto3.client") as mock_client_factory:
        mock_client = _ClientErrorMock()
        mock_client_factory.return_value = mock_client

        provider = BedrockProvider()
        health = await provider.health_check()

        assert health.is_healthy is False
        assert health.error_message is not None
        assert len(health.error_message) > 0


# --- Test 7: BedrockProvider implements LLMProvider protocol ---
def test_bedrock_implements_llm_provider_protocol() -> None:
    """BedrockProvider implements LLMProvider protocol (runtime_checkable check)."""
    with patch("boto3.client"):
        provider = BedrockProvider()
        assert isinstance(provider, LLMProvider)


# --- Test 8: ModelRouter routes BLOCKER_SCAN to bedrock with correct model_id ---
def test_default_role_routing_blocker_scan_bedrock() -> None:
    """DEFAULT_ROLE_ROUTING routes BLOCKER_SCAN to bedrock with haiku profile."""
    routing = DEFAULT_ROLE_ROUTING[ModelRole.BLOCKER_SCAN]
    assert routing.primary == "bedrock"
    assert routing.fallback == "anthropic"
    assert routing.model_id == "global.anthropic.claude-haiku-4-5-20251001-v1:0"


# --- Test 9: ModelRouter fallback on BedrockProvider failure ---
@pytest.mark.asyncio
async def test_model_router_fallback_to_anthropic(
    audit_ledger: AuditLedger,
) -> None:
    """ModelRouter falls back to anthropic if BedrockProvider raises ProviderError."""
    failing_bedrock = _FailingBedrockProvider()

    success_response = LLMResponse(
        text="Fallback response",
        model_name="claude-sonnet-4-5",
        input_tokens=5,
        output_tokens=10,
        latency_ms=100,
        provider_name="anthropic",
    )

    class _SuccessfulAnthropicMock:
        async def complete(
            self,
            prompt: str,
            system: str,
            max_tokens: int,
            temperature: float,
        ) -> LLMResponse:
            return success_response

        async def health_check(self) -> ProviderHealth:
            from datetime import UTC, datetime

            return ProviderHealth(
                is_healthy=True,
                latency_ms=50,
                last_checked=datetime.now(UTC),
            )

    config = ModelRouterConfig(
        providers={
            "bedrock": ProviderConfig(
                name="bedrock",
                model_name=BEDROCK_MODEL_IDS["claude-sonnet"],
            ),
            "anthropic": ProviderConfig(
                name="anthropic",
                model_name="claude-sonnet-4-5",
            ),
        },
        role_routing={
            ModelRole.BLOCKER_SCAN: RoleRouting(
                primary="bedrock",
                fallback="anthropic",
            ),
            ModelRole.TRADE_CARD: RoleRouting(
                primary="bedrock",
                fallback="anthropic",
            ),
            ModelRole.EXPLANATION: RoleRouting(
                primary="bedrock",
                fallback="anthropic",
            ),
        },
    )

    telemetry = ModelTelemetry()
    router = ModelRouter(
        config=config,
        providers={
            "bedrock": failing_bedrock,
            "anthropic": _SuccessfulAnthropicMock(),
        },
        audit_ledger=audit_ledger,
        telemetry=telemetry,
        mode=Mode.LIVE,
    )

    response = await router.complete(
        ModelRole.BLOCKER_SCAN,
        "test prompt",
        "test system",
    )

    assert response.provider_name == "anthropic"
    assert response.text == "Fallback response"


# --- Test 10: AppState skips BedrockProvider if AWS_REGION not set ---
def test_build_providers_skips_bedrock_without_aws_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_build_providers skips BedrockProvider when AWS_REGION not set."""
    monkeypatch.delenv("AWS_REGION", raising=False)

    with patch("boto3.client"):
        # Import at runtime — the module is in apps/api/src/services/
        from importlib import import_module

        try:
            app_state_module = import_module("services.app_state")
            _build_providers = app_state_module._build_providers
        except (ImportError, AttributeError):
            pytest.skip("services.app_state not available in test environment")
            return

        providers = _build_providers(Mode.LIVE)

        # Should have anthropic and openai, but not bedrock
        assert "anthropic" in providers
        assert "openai" in providers
        assert "bedrock" not in providers


# --- Test 11: BedrockProvider instantiated when AWS_REGION is set ---
def test_build_providers_includes_bedrock_with_aws_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_build_providers includes BedrockProvider when AWS_REGION is set."""
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("BEDROCK_MODEL_ID", BEDROCK_MODEL_IDS["claude-haiku"])

    with patch("boto3.client"):
        # Import at runtime — the module is in apps/api/src/services/
        from importlib import import_module

        try:
            app_state_module = import_module("services.app_state")
            _build_providers = app_state_module._build_providers
        except (ImportError, AttributeError):
            pytest.skip("services.app_state not available in test environment")
            return

        providers = _build_providers(Mode.LIVE)

        # Should have all three providers
        assert "anthropic" in providers
        assert "openai" in providers
        assert "bedrock" in providers
        assert isinstance(providers["bedrock"], BedrockProvider)


# --- Test 12: ModelRouter respects DEFAULT_ROLE_ROUTING ---
@pytest.mark.asyncio
async def test_model_router_uses_default_routing(
    audit_ledger: AuditLedger,
) -> None:
    """ModelRouter with bedrock config routes TRADE_CARD to bedrock with sonnet."""
    with patch("boto3.client") as mock_client_factory:
        mock_client = _SuccessfulBedrockMock()
        mock_client_factory.return_value = mock_client

        config = ModelRouterConfig(
            providers={
                "bedrock": ProviderConfig(
                    name="bedrock",
                    model_name=BEDROCK_MODEL_IDS["claude-sonnet"],
                ),
            },
            role_routing={
                ModelRole.TRADE_CARD: RoleRouting(
                    primary="bedrock",
                    model_id=BEDROCK_MODEL_IDS["claude-sonnet"],
                ),
                ModelRole.BLOCKER_SCAN: RoleRouting(
                    primary="bedrock",
                    model_id=BEDROCK_MODEL_IDS["claude-haiku"],
                ),
                ModelRole.EXPLANATION: RoleRouting(
                    primary="bedrock",
                    model_id=BEDROCK_MODEL_IDS["claude-haiku"],
                ),
            },
        )

        telemetry = ModelTelemetry()
        provider = BedrockProvider()
        router = ModelRouter(
            config=config,
            providers={"bedrock": provider},
            audit_ledger=audit_ledger,
            telemetry=telemetry,
            mode=Mode.LIVE,
        )

        response = await router.complete(
            ModelRole.TRADE_CARD,
            "test prompt",
            "test system",
        )

        assert response.provider_name == "bedrock"
        assert response.text == "Mock response from Bedrock"


# --- Test 13: RoleRouting with model_id field ---
def test_role_routing_has_model_id_field() -> None:
    """RoleRouting includes optional model_id field."""
    routing = RoleRouting(
        primary="bedrock",
        fallback="anthropic",
        model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
    )
    assert routing.model_id == "anthropic.claude-3-5-haiku-20241022-v1:0"


# --- Test 14: RoleRouting model_id is optional ---
def test_role_routing_model_id_optional() -> None:
    """RoleRouting model_id is optional and defaults to None."""
    routing = RoleRouting(primary="bedrock", fallback="anthropic")
    assert routing.model_id is None


# --- Test 15: BEDROCK_MODEL_IDS dict contains expected models ---
def test_bedrock_model_ids() -> None:
    """BEDROCK_MODEL_IDS contains both Sonnet and Haiku inference profile IDs."""
    assert "claude-sonnet" in BEDROCK_MODEL_IDS
    assert "claude-haiku" in BEDROCK_MODEL_IDS
    assert (
        BEDROCK_MODEL_IDS["claude-sonnet"]
        == "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
    )
    assert (
        BEDROCK_MODEL_IDS["claude-haiku"]
        == "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    )
