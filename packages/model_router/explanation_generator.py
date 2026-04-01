"""Explanation generator — produces plain-language explanations via LLM."""

from __future__ import annotations

import logging
from decimal import Decimal

from packages.contracts.decisions import EntryDecision, ExitDecision
from packages.contracts.llm import ExplanationOutput, ModelRole

from .parser import StructuredOutputParser
from .prompts import explanation
from .router import ModelRouter

logger = logging.getLogger(__name__)

_SAFE_DEFAULT = ExplanationOutput(
    plain_language="Explanation unavailable",
    confidence=Decimal("0.0"),
    key_factors=[],
)


class ExplanationGenerator:
    """Generates plain-language explanations of trade decisions.

    On any failure, returns a safe default — explanations are operator UX,
    a missing explanation should never block a trade.
    """

    def __init__(
        self,
        router: ModelRouter,
        parser: StructuredOutputParser,
    ) -> None:
        self._router = router
        self._parser = parser

    async def explain_entry(
        self, decision: EntryDecision
    ) -> ExplanationOutput:
        """Explain an entry decision."""
        system = explanation.build_system_prompt()
        prompt = explanation.build_entry_prompt(
            symbol=decision.symbol,
            layer=decision.layer.value,
            decision=decision.decision,
            checks_performed=decision.checks_performed,
            rejection_reasons=decision.rejection_reasons,
        )

        try:
            response = await self._router.complete(
                role=ModelRole.EXPLANATION,
                prompt=prompt,
                system=system,
            )
            return self._parser.parse_explanation(response.text)
        except Exception:
            logger.exception(
                "Explanation generation failed for entry %s", decision.symbol
            )
            return _SAFE_DEFAULT

    async def explain_exit(
        self, decision: ExitDecision
    ) -> ExplanationOutput:
        """Explain an exit decision."""
        system = explanation.build_system_prompt()
        prompt = explanation.build_exit_prompt(
            symbol=decision.symbol,
            layer=decision.layer.value,
            decision=decision.decision,
            exit_reason=decision.exit_reason,
        )

        try:
            response = await self._router.complete(
                role=ModelRole.EXPLANATION,
                prompt=prompt,
                system=system,
            )
            return self._parser.parse_explanation(response.text)
        except Exception:
            logger.exception(
                "Explanation generation failed for exit %s", decision.symbol
            )
            return _SAFE_DEFAULT
