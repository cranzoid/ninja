"""Model router — routes LLM requests to providers with fallback logic."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from packages.contracts.audit_event import AuditEvent
from packages.contracts.enums import Mode
from packages.contracts.llm import (
    LLMResponse,
    ModelRole,
    ModelRouterConfig,
    ProviderHealth,
    RoutingDecision,
)
from services.audit_ledger.ledger import AuditLedger

from .providers.base import AllProvidersFailedError, LLMProvider, ProviderError
from .telemetry import ModelTelemetry

logger = logging.getLogger(__name__)

# Default token limits and temperatures per role
_ROLE_DEFAULTS: dict[ModelRole, tuple[int, float]] = {
    ModelRole.BLOCKER_SCAN: (1024, 0.0),
    ModelRole.TRADE_CARD: (2048, 0.1),
    ModelRole.EXPLANATION: (1024, 0.3),
    ModelRole.CRITIQUE: (2048, 0.2),
}


class ModelRouter:
    """Routes LLM requests to providers with automatic fallback."""

    def __init__(
        self,
        config: ModelRouterConfig,
        providers: dict[str, LLMProvider],
        audit_ledger: AuditLedger,
        telemetry: ModelTelemetry,
        mode: Mode = Mode.PAPER,
    ) -> None:
        self._config = config
        self._providers = providers
        self._audit_ledger = audit_ledger
        self._telemetry = telemetry
        self._mode = mode

    async def complete(
        self,
        role: ModelRole,
        prompt: str,
        system: str,
    ) -> LLMResponse:
        """Route a request to the appropriate provider with fallback."""
        routing = self._config.role_routing.get(role)
        if routing is None:
            raise ValueError(f"No routing configured for role {role}")

        max_tokens, temperature = _ROLE_DEFAULTS.get(role, (1024, 0.0))

        # Inject role metadata for fixture provider detection
        augmented_system = f"[MODEL_ROLE={role.value}]\n{system}"

        primary_name = routing.primary
        fallback_name = routing.fallback

        errors: list[ProviderError] = []

        # Try primary
        primary_provider = self._providers.get(primary_name)
        if primary_provider is not None:
            try:
                response = await primary_provider.complete(
                    prompt=prompt,
                    system=augmented_system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                decision = RoutingDecision(
                    role=role,
                    chosen_provider=primary_name,
                    fallback_used=False,
                    reason="primary_success",
                )
                await self._log_routing_decision(decision, response.latency_ms)
                self._telemetry.record_success(
                    role, primary_name, response.latency_ms, fallback_used=False
                )
                return response
            except ProviderError as exc:
                errors.append(exc)
                self._telemetry.record_failure(role, primary_name, 0)
                logger.warning(
                    "Primary provider %s failed for role %s: %s",
                    primary_name,
                    role,
                    exc,
                )

        # Try fallback
        if fallback_name:
            fallback_provider = self._providers.get(fallback_name)
            if fallback_provider is not None:
                try:
                    response = await fallback_provider.complete(
                        prompt=prompt,
                        system=system,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    decision = RoutingDecision(
                        role=role,
                        chosen_provider=fallback_name,
                        fallback_used=True,
                        reason=f"primary '{primary_name}' failed, using fallback",
                    )
                    await self._log_routing_decision(
                        decision, response.latency_ms
                    )
                    self._telemetry.record_success(
                        role, fallback_name, response.latency_ms, fallback_used=True
                    )
                    return response
                except ProviderError as exc:
                    errors.append(exc)
                    self._telemetry.record_failure(role, fallback_name, 0)
                    logger.error(
                        "Fallback provider %s also failed for role %s: %s",
                        fallback_name,
                        role,
                        exc,
                    )

        # Both failed
        all_failed_error = AllProvidersFailedError(errors)
        await self._log_all_providers_failed(role, errors)
        raise all_failed_error

    async def health_check_all(self) -> dict[str, ProviderHealth]:
        """Run health checks on all configured providers."""
        results: dict[str, ProviderHealth] = {}
        for name, provider in self._providers.items():
            try:
                results[name] = await provider.health_check()
            except Exception as exc:
                from datetime import UTC, datetime

                results[name] = ProviderHealth(
                    is_healthy=False,
                    latency_ms=0,
                    last_checked=datetime.now(UTC),
                    error_message=str(exc),
                )
                await self._log_health_check_failure(name, exc)
        return results

    async def _log_routing_decision(
        self, decision: RoutingDecision, latency_ms: int
    ) -> None:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            event_type="model_routing_decision",
            source_service="model-router",
            mode=self._mode,
            payload={
                "role": decision.role.value,
                "chosen_provider": decision.chosen_provider,
                "fallback_used": decision.fallback_used,
                "reason": decision.reason,
                "latency_ms": latency_ms,
            },
            operator_visible=False,
        )
        await self._audit_ledger.record(event)

    async def _log_all_providers_failed(
        self, role: ModelRole, errors: list[ProviderError]
    ) -> None:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            event_type="all_providers_failed",
            source_service="model-router",
            mode=self._mode,
            payload={
                "role": role.value,
                "providers_tried": [e.provider_name for e in errors],
                "errors": [str(e.original_error) for e in errors],
            },
            operator_visible=True,
        )
        await self._audit_ledger.record(event)

    async def _log_health_check_failure(
        self, provider_name: str, error: Exception
    ) -> None:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            event_type="health_check_failure",
            source_service="model-router",
            mode=self._mode,
            payload={
                "provider": provider_name,
                "error": str(error),
            },
            operator_visible=True,
        )
        await self._audit_ledger.record(event)
