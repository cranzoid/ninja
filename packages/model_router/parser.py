"""Structured output parser — validates LLM outputs against Pydantic contracts."""

from __future__ import annotations

import re

from packages.contracts.blocker_report import BlockerReport
from packages.contracts.llm import ExplanationOutput, ModelRole
from packages.contracts.trade_card import TradeCard
from packages.contracts.validators import validate_json_string


class OutputParseError(Exception):
    """Raised when LLM output cannot be parsed into the expected contract."""

    def __init__(
        self,
        role: ModelRole,
        raw_output: str,
        validation_errors: list[str],
    ) -> None:
        self.role = role
        self.raw_output = raw_output
        self.validation_errors = validation_errors
        super().__init__(
            f"Failed to parse {role} output: {'; '.join(validation_errors)}"
        )


def _extract_json(raw: str) -> str:
    """Extract JSON from raw LLM output, handling markdown code fences."""
    # Try to extract from ```json ... ``` or ``` ... ``` blocks
    fence_match = re.search(
        r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL
    )
    if fence_match:
        return fence_match.group(1).strip()

    # Try to find raw JSON object
    stripped = raw.strip()
    if stripped.startswith("{"):
        return stripped

    # Last resort: find first { to last }
    first_brace = raw.find("{")
    last_brace = raw.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return raw[first_brace : last_brace + 1]

    return stripped


class StructuredOutputParser:
    """Parses and validates LLM outputs against Pydantic contracts."""

    def parse_blocker_report(self, raw: str, symbol: str) -> BlockerReport:
        """Parse raw LLM output into a BlockerReport."""
        json_str = _extract_json(raw)
        result, errors = validate_json_string(json_str, BlockerReport)
        if result is None:
            raise OutputParseError(ModelRole.BLOCKER_SCAN, raw, errors)
        return result

    def parse_trade_card(self, raw: str) -> TradeCard:
        """Parse raw LLM output into a TradeCard."""
        json_str = _extract_json(raw)
        result, errors = validate_json_string(json_str, TradeCard)
        if result is None:
            raise OutputParseError(ModelRole.TRADE_CARD, raw, errors)
        return result

    def parse_explanation(self, raw: str) -> ExplanationOutput:
        """Parse raw LLM output into an ExplanationOutput."""
        json_str = _extract_json(raw)
        result, errors = validate_json_string(json_str, ExplanationOutput)
        if result is None:
            raise OutputParseError(ModelRole.EXPLANATION, raw, errors)
        return result
