"""Fixture LLM provider — deterministic canned responses for tests.

Never makes network calls. Returns pre-defined JSON responses per ModelRole.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime

from packages.contracts.llm import LLMResponse, ModelRole, ProviderHealth

_PROVIDER_NAME = "fixture"
_MODEL_NAME = "fixture-model-v1"


def _blocker_report_json(symbol: str = "RELIANCE") -> str:
    return json.dumps(
        {
            "symbol": symbol,
            "scan_timestamp": datetime.now(UTC).isoformat(),
            "blockers_found": [],
            "is_blocked": False,
            "model_provider": _PROVIDER_NAME,
            "model_id": _MODEL_NAME,
        }
    )


def _blocker_report_with_blocker_json(symbol: str = "HDFCBANK") -> str:
    return json.dumps(
        {
            "symbol": symbol,
            "scan_timestamp": datetime.now(UTC).isoformat(),
            "blockers_found": [
                {
                    "category": "earnings_window",
                    "severity": "hard",
                    "reason": "Q4 results in 3 days. Blocked per rule S1.",
                    "source_category": "earnings_calendar",
                    "expires_at": "2026-04-01T00:00:00Z",
                }
            ],
            "is_blocked": True,
            "model_provider": _PROVIDER_NAME,
            "model_id": _MODEL_NAME,
        }
    )


def _trade_card_json() -> str:
    return json.dumps(
        {
            "symbol": "RELIANCE",
            "layer": "swing",
            "direction": "long",
            "thesis_summary": "Reliance 20-day breakout on elevated volume.",
            "entry_price_target": "2850.00",
            "stop_price": "2780.00",
            "risk_per_share": "70.00",
            "reward_target_1": "2990.00",
            "atr_14": "45.00",
            "dma_200": "2650.00",
            "dma_50": "2720.00",
            "volume_ratio_20d": "1.45",
            "regime_at_generation": "green",
            "generated_at": datetime.now(UTC).isoformat(),
            "model_provider": _PROVIDER_NAME,
            "model_id": _MODEL_NAME,
            "confidence_tag": "high",
        }
    )


def _explanation_json() -> str:
    return json.dumps(
        {
            "plain_language": (
                "RELIANCE passed all entry conditions. "
                "20-day high breakout with volume confirmation in a green regime."
            ),
            "confidence": "0.85",
            "key_factors": [
                "20-day high breakout",
                "Volume ratio 1.45x above average",
                "Green regime — full sizing",
            ],
        }
    )


# Mapping: role → canned response text
_CANNED_RESPONSES: dict[str, str] = {
    ModelRole.BLOCKER_SCAN: _blocker_report_json(),
    ModelRole.TRADE_CARD: _trade_card_json(),
    ModelRole.EXPLANATION: _explanation_json(),
}


class FixtureProvider:
    """Deterministic LLM provider for tests — never makes network calls."""

    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        self._model_name = model_name

    async def complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        start = time.monotonic()

        # Determine role from system prompt content
        role = self._detect_role(system, prompt)
        text = self._get_canned_response(role, prompt)

        latency_ms = int((time.monotonic() - start) * 1000)

        return LLMResponse(
            text=text,
            model_name=self._model_name,
            input_tokens=len(prompt.split()),
            output_tokens=len(text.split()),
            latency_ms=max(latency_ms, 1),
            provider_name=_PROVIDER_NAME,
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            is_healthy=True,
            latency_ms=1,
            last_checked=datetime.now(UTC),
        )

    def _detect_role(self, system: str, prompt: str) -> str:
        """Detect the model role from prompt content."""
        # Check for role metadata injected by ModelRouter
        import re

        role_match = re.search(
            r"\[MODEL_ROLE=(\w+)\]", system
        )
        if role_match:
            role_value = role_match.group(1)
            try:
                return ModelRole(role_value)
            except ValueError:
                pass

        # Fallback: detect from prompt text
        system_lower = system.lower()
        if "thesis" in system_lower:
            return ModelRole.TRADE_CARD
        if "explanation" in system_lower or "explain" in system_lower:
            return ModelRole.EXPLANATION
        return ModelRole.BLOCKER_SCAN

    def _get_canned_response(self, role: str, prompt: str) -> str:
        """Return a deterministic canned response for the role."""
        if role == ModelRole.BLOCKER_SCAN:
            # Extract symbol from prompt if present
            symbol = self._extract_symbol(prompt)
            if symbol == "HDFCBANK":
                return _blocker_report_with_blocker_json(symbol)
            return _blocker_report_json(symbol)
        return _CANNED_RESPONSES.get(role, _CANNED_RESPONSES[ModelRole.BLOCKER_SCAN])

    def _extract_symbol(self, prompt: str) -> str:
        """Try to extract a symbol from the prompt text."""
        # Look for "Symbol: XXX" pattern
        for line in prompt.split("\n"):
            if line.strip().lower().startswith("symbol:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
        return "RELIANCE"
