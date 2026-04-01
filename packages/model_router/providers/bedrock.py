"""AWS Bedrock provider for the model router.

Uses boto3 converse API — works with Claude models on Bedrock.
Implements LLMProvider protocol exactly.
Charter §7.5: Bedrock-first for production.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import boto3
import botocore.exceptions

from packages.contracts.llm import LLMResponse, ProviderHealth

from .base import ProviderError

logger = logging.getLogger(__name__)

_PROVIDER_NAME = "bedrock"
_IST = ZoneInfo("Asia/Kolkata")

BEDROCK_MODEL_IDS: dict[str, str] = {
    "claude-sonnet": (
        "anthropic.claude-3-5-sonnet-20241022-v2:0"  # Tier 2 — hard reasoning
    ),
    "claude-haiku": (
        "anthropic.claude-3-5-haiku-20241022-v1:0"  # Tier 1/3 — fast, cheap
    ),
}


class BedrockProvider:
    """
    AWS Bedrock provider for the model router.
    Uses boto3 converse API — works with Claude models on Bedrock.
    Implements LLMProvider protocol exactly.
    Charter §7.5: Bedrock-first for production.
    """

    def __init__(
        self,
        model_id: str = BEDROCK_MODEL_IDS["claude-sonnet"],
    ) -> None:
        self._model_id = model_id
        region = os.environ.get("AWS_REGION", "ap-south-1")
        # boto3 reads AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY automatically
        self._client: Any = boto3.client("bedrock-runtime", region_name=region)

    def _call_converse(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> Any:
        """Synchronous converse call — run via asyncio.to_thread."""
        kwargs: dict[str, Any] = {
            "modelId": self._model_id,
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
        }
        if system:
            kwargs["system"] = [{"text": system}]
        return self._client.converse(**kwargs)

    def _health_call(self) -> None:
        """Minimal synchronous converse call for health check."""
        self._client.converse(
            modelId=self._model_id,
            messages=[{"role": "user", "content": [{"text": "ping"}]}],
            inferenceConfig={"maxTokens": 1},
        )

    async def complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        start = time.monotonic()
        try:
            response = await asyncio.to_thread(
                self._call_converse, prompt, system, max_tokens, temperature
            )
            latency_ms = int((time.monotonic() - start) * 1000)

            message_content = response["output"]["message"]["content"]
            text = message_content[0]["text"] if message_content else ""
            usage = response["usage"]

            logger.info(
                "Bedrock call: model=%s latency=%dms tokens_in=%d tokens_out=%d",
                self._model_id,
                latency_ms,
                usage["inputTokens"],
                usage["outputTokens"],
            )

            return LLMResponse(
                text=text,
                model_name=self._model_id,
                input_tokens=usage["inputTokens"],
                output_tokens=usage["outputTokens"],
                latency_ms=latency_ms,
                provider_name=_PROVIDER_NAME,
            )
        except (
            botocore.exceptions.ClientError,
            botocore.exceptions.EndpointConnectionError,
        ) as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "Bedrock call failed: model=%s latency=%dms error=%s",
                self._model_id,
                latency_ms,
                exc,
            )
            raise ProviderError(_PROVIDER_NAME, exc) from exc
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "Bedrock unexpected error: model=%s latency=%dms error=%s",
                self._model_id,
                latency_ms,
                exc,
            )
            raise ProviderError(_PROVIDER_NAME, exc) from exc

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            await asyncio.to_thread(self._health_call)
            latency_ms = int((time.monotonic() - start) * 1000)
            return ProviderHealth(
                is_healthy=True,
                latency_ms=latency_ms,
                last_checked=datetime.now(_IST),
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            return ProviderHealth(
                is_healthy=False,
                latency_ms=latency_ms,
                last_checked=datetime.now(_IST),
                error_message=str(exc),
            )
