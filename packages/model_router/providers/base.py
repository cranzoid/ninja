"""Base LLM provider protocol and exceptions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from packages.contracts.llm import LLMResponse, ProviderHealth


class ProviderError(Exception):
    """Raised when an LLM provider fails."""

    def __init__(self, provider_name: str, original_error: Exception) -> None:
        self.provider_name = provider_name
        self.original_error = original_error
        super().__init__(
            f"Provider '{provider_name}' failed: {original_error}"
        )


class AllProvidersFailedError(Exception):
    """Raised when all providers (primary + fallback) fail."""

    def __init__(self, errors: list[ProviderError]) -> None:
        self.errors = errors
        provider_names = [e.provider_name for e in errors]
        super().__init__(
            f"All providers failed: {', '.join(provider_names)}"
        )


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM provider implementations."""

    async def complete(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse: ...

    async def health_check(self) -> ProviderHealth: ...
