"""EnvVarsCheck — verifies required environment variables are present."""

from __future__ import annotations

from datetime import UTC, datetime

from packages.contracts.compliance import (
    ComplianceContext,
    ComplianceResult,
    ComplianceStatus,
)
from packages.contracts.enums import Mode

# LLM keys — warn in paper, block in live
_LLM_KEYS = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"]

# Broker keys — only required in shadow-live / live
_BROKER_KEYS = ["ZERODHA_API_KEY", "ZERODHA_API_SECRET", "STATIC_IP_WHITELIST"]


class EnvVarsCheck:
    """Verifies all required env vars are present for the current mode."""

    name: str = "env_vars"
    description: str = "Required environment variables are set"
    blocking: bool = True

    async def run(self, context: ComplianceContext) -> ComplianceResult:
        now = datetime.now(UTC)
        present = set(context.env_vars_present)

        if context.mode == Mode.PAPER:
            missing_llm = [k for k in _LLM_KEYS if k not in present]
            if missing_llm:
                return ComplianceResult(
                    check_name=self.name,
                    status=ComplianceStatus.WARNING,
                    message=(
                        "LLM keys missing (non-blocking in paper): "
                        f"{', '.join(missing_llm)}"
                    ),
                    checked_at=now,
                )
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.PASS,
                message="All paper-mode env vars present.",
                checked_at=now,
            )

        # Shadow-live or live
        missing_broker = [k for k in _BROKER_KEYS if k not in present]
        if missing_broker:
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.FAIL,
                message=f"Missing required broker env vars: {', '.join(missing_broker)}",
                checked_at=now,
            )

        # LLM keys are only required when Bedrock is not configured
        bedrock_available = "AWS_REGION" in present
        if not bedrock_available:
            missing_llm = [k for k in _LLM_KEYS if k not in present]
            if missing_llm:
                return ComplianceResult(
                    check_name=self.name,
                    status=ComplianceStatus.FAIL,
                    message=(
                        f"Missing LLM env vars (set AWS_REGION to use Bedrock instead): "
                        f"{', '.join(missing_llm)}"
                    ),
                    checked_at=now,
                )

        return ComplianceResult(
            check_name=self.name,
            status=ComplianceStatus.PASS,
            message="All required env vars present.",
            checked_at=now,
        )
