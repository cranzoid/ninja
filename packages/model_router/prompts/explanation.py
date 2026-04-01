"""Prompt templates for the explanation generation model role."""

from __future__ import annotations

import json

from packages.contracts.llm import ExplanationOutput


def build_system_prompt() -> str:
    """Build the system prompt for explanation generation."""
    schema = json.dumps(
        ExplanationOutput.model_json_schema(), indent=2
    )
    return (
        "You are an explanation generator for an Indian"
        " equities trading system.\n\n"
        "Your role is to produce a plain-language explanation"
        " of a trade decision for the operator.\n\n"
        "AUDIENCE:\n"
        "- The operator is a solo trader with"
        " institutional-level knowledge\n"
        "- Not retail-level simplification,"
        " not academic jargon\n"
        "- Concise, direct, actionable language\n\n"
        "OUTPUT RULES:\n"
        "- plain_language: 1-3 sentences explaining"
        " the decision and its drivers\n"
        "- confidence: 0.0 to 1.0, reflecting"
        " the strength of the decision\n"
        "- key_factors: 3-5 bullet points listing"
        " the most important factors\n"
        "- Output ONLY valid JSON matching the schema"
        " below. No other text.\n\n"
        f"OUTPUT SCHEMA:\n{schema}"
    )


def build_entry_prompt(
    symbol: str,
    layer: str,
    decision: str,
    checks_performed: list[str],
    rejection_reasons: list[str],
) -> str:
    """Build the user prompt for entry decision explanation."""
    checks_text = "\n".join(f"- {c}" for c in checks_performed)
    reasons_text = (
        "\n".join(f"- {r}" for r in rejection_reasons)
        if rejection_reasons
        else "None"
    )

    return (
        "Explain the following entry decision:\n\n"
        f"Symbol: {symbol}\n"
        f"Layer: {layer}\n"
        f"Decision: {decision}\n\n"
        f"Checks Performed:\n{checks_text}\n\n"
        f"Rejection Reasons:\n{reasons_text}\n\n"
        "Provide a plain-language explanation as valid JSON."
    )


def build_exit_prompt(
    symbol: str,
    layer: str,
    decision: str,
    exit_reason: str | None,
) -> str:
    """Build the user prompt for exit decision explanation."""
    return (
        "Explain the following exit decision:\n\n"
        f"Symbol: {symbol}\n"
        f"Layer: {layer}\n"
        f"Decision: {decision}\n"
        f"Exit Reason: {exit_reason or 'N/A'}\n\n"
        "Provide a plain-language explanation as valid JSON."
    )
