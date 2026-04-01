"""Anthropic LLM provider — wraps the Anthropic SDK."""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime

from packages.contracts.llm import LLMResponse, ProviderHealth

from .base import ProviderError

logger = logging.getLogger(__name__)

_PROVIDER_NAME = "anthropic"


class AnthropicProvider:
    """LLM provider using the Anthropic API (Claude models)."""

    def __init__(
        self,
        model_name: str = "claude-sonnet-4-5",
        timeout_seconds: int = 30,
        max_retries: int = 2,
    ) -> None:
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set — calls will fail")
        try:
            import anthropic

            self._client = anthropic.AsyncAnthropic(
                api_key=api_key,
                timeout=float(timeout_seconds),
                max_retries=max_retries,
            )
        except ImportError:
            logger.warning("anthropic package not installed")
            self._client = None

    async def complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        if self._client is None:
            raise ProviderError(
                _PROVIDER_NAME,
                RuntimeError("anthropic package not installed"),
            )

        start = time.monotonic()
        try:
            response = await self._client.messages.create(
                model=self._model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            latency_ms = int((time.monotonic() - start) * 1000)

            text = response.content[0].text if response.content else ""
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            logger.info(
                "Anthropic call: model=%s latency=%dms tokens_in=%d tokens_out=%d",
                self._model_name,
                latency_ms,
                input_tokens,
                output_tokens,
            )

            return LLMResponse(
                text=text,
                model_name=self._model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                provider_name=_PROVIDER_NAME,
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "Anthropic call failed: model=%s latency=%dms error=%s",
                self._model_name,
                latency_ms,
                exc,
            )
            raise ProviderError(_PROVIDER_NAME, exc) from exc

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            if self._client is None:
                raise RuntimeError("anthropic package not installed")
            # Minimal call to check connectivity
            await self._client.messages.create(
                model=self._model_name,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            return ProviderHealth(
                is_healthy=True,
                latency_ms=latency_ms,
                last_checked=datetime.now(UTC),
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            return ProviderHealth(
                is_healthy=False,
                latency_ms=latency_ms,
                last_checked=datetime.now(UTC),
                error_message=str(exc),
            )
