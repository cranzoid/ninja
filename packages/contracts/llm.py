"""LLM integration contracts — Phase 5 model routing schemas."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator


class ModelRole(StrEnum):
    """AI model roles from charter §7.2."""

    BLOCKER_SCAN = "blocker_scan"
    TRADE_CARD = "trade_card"
    EXPLANATION = "explanation"
    CRITIQUE = "critique"  # Reserved for Phase 6


class LLMResponse(BaseModel):
    """Raw response from an LLM provider."""

    model_config = ConfigDict(strict=True, frozen=True)

    text: str
    """Raw text output from the model."""

    model_name: str
    """Model identifier, e.g. 'claude-sonnet-4-5'."""

    input_tokens: int
    output_tokens: int
    latency_ms: int
    provider_name: str


class ProviderHealth(BaseModel):
    """Health check result for a single LLM provider."""

    model_config = ConfigDict(strict=True, frozen=True)

    is_healthy: bool
    latency_ms: int
    last_checked: datetime
    """IST timestamp of last health check."""

    error_message: str | None = None


class RoutingDecision(BaseModel):
    """Record of a model routing decision."""

    model_config = ConfigDict(strict=True, frozen=True)

    role: ModelRole
    chosen_provider: str
    fallback_used: bool
    reason: str


class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""

    model_config = ConfigDict(strict=True, frozen=True)

    name: str
    """Provider name: 'anthropic', 'openai', 'fixture'."""

    model_name: str
    """Model to use, e.g. 'claude-sonnet-4-5', 'gpt-4o'."""

    timeout_seconds: int = 30
    max_retries: int = 2


class RoleRouting(BaseModel):
    """Routing configuration for a single model role."""

    model_config = ConfigDict(strict=True, frozen=True)

    primary: str
    """Primary provider name."""

    fallback: str | None = None
    """Optional fallback provider name."""

    model_id: str | None = None
    """Model ID hint for the provider, e.g. a Bedrock model ARN."""


class ModelRouterConfig(BaseModel):
    """Configuration for the model router."""

    model_config = ConfigDict(strict=True, frozen=True)

    providers: dict[str, ProviderConfig]
    """Provider name → config mapping."""

    role_routing: dict[ModelRole, RoleRouting]
    """Role → routing config mapping."""


class ExplanationOutput(BaseModel):
    """Structured explanation of a trade decision for the operator."""

    model_config = ConfigDict(strict=True, frozen=True)

    plain_language: str
    """1-3 sentence explanation in operator-friendly language."""

    confidence: Decimal
    """Confidence score 0.0-1.0."""

    key_factors: list[str]
    """List of key factors that drove the decision."""

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, v: Decimal) -> Decimal:
        if v < Decimal("0.0") or v > Decimal("1.0"):
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v


class ProviderRoleStats(BaseModel):
    """Telemetry stats for a single provider+role combination."""

    model_config = ConfigDict(strict=True, frozen=True)

    provider: str
    role: ModelRole
    total_calls: int
    success_count: int
    failure_count: int
    avg_latency_ms: float
    p95_latency_ms: float
    fallback_rate: float
    parse_failure_rate: float


class ModelTelemetrySummary(BaseModel):
    """Aggregated telemetry summary across all providers and roles."""

    model_config = ConfigDict(strict=True, frozen=True)

    stats: list[ProviderRoleStats]
    total_calls: int
    overall_success_rate: float
    overall_fallback_rate: float


# Default routing — Bedrock primary, direct Anthropic as fallback.
# Charter §7.5: Bedrock-first for production.
# Tier 1/3 roles → Haiku; Tier 2 roles → Sonnet.
DEFAULT_ROLE_ROUTING: dict[ModelRole, RoleRouting] = {
    ModelRole.BLOCKER_SCAN: RoleRouting(
        primary="bedrock",
        fallback="anthropic",
        model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0",
    ),
    ModelRole.TRADE_CARD: RoleRouting(
        primary="bedrock",
        fallback="anthropic",
        model_id="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    ),
    ModelRole.EXPLANATION: RoleRouting(
        primary="bedrock",
        fallback="openai",
        model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0",
    ),
    ModelRole.CRITIQUE: RoleRouting(
        primary="bedrock",
        fallback="anthropic",
        model_id="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    ),
}
