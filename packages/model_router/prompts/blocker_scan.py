"""Prompt templates for the blocker scan model role."""

from __future__ import annotations

import json

from packages.contracts.blocker_report import BlockerReport


def build_system_prompt() -> str:
    """Build the system prompt for blocker scanning."""
    schema = json.dumps(
        BlockerReport.model_json_schema(), indent=2
    )
    return (
        "You are a blocker classifier for an Indian equities"
        " trading system.\n\n"
        "Your role is to analyze a symbol and its recent"
        " headlines to determine if any blockers"
        " prevent entry.\n\n"
        "A blocker is an event or condition that should prevent"
        " a new position from being opened."
        " The following constitute blockers:\n\n"
        'HARD BLOCKERS (severity: "hard") -- absolute blocks:\n'
        '- Earnings within 5 trading days (category: "earnings_window")\n'
        "- Open regulatory investigations"
        ' (category: "credibility_risk")\n'
        "- Recent profit warnings or guidance cuts"
        ' (category: "credibility_risk")\n'
        "- Trading halts or suspensions"
        ' (category: "corporate_action")\n\n'
        'SOFT BLOCKERS (severity: "soft") -- flag for operator review:\n'
        '- Senior management changes (category: "credibility_risk")\n'
        "- Pending corporate actions like splits, mergers"
        ' (category: "corporate_action")\n'
        "- Sector-wide shocks affecting the stock"
        ' (category: "sector_shock")\n\n'
        "RULES:\n"
        "- is_blocked must be True if and only if"
        " at least one HARD blocker is found\n"
        "- If no blockers are found, return an empty"
        " blockers_found list and is_blocked=False\n"
        "- Always set model_provider and model_id"
        " to match your identity\n"
        "- Output ONLY valid JSON matching the schema below."
        " No other text.\n\n"
        f"OUTPUT SCHEMA:\n{schema}"
    )


def build_user_prompt(
    symbol: str,
    company_name: str,
    headlines: list[str],
    last_price: float,
    atr: float,
) -> str:
    """Build the user prompt for blocker scanning."""
    if headlines:
        headlines_text = "\n".join(f"- {h}" for h in headlines)
    else:
        headlines_text = "- No recent headlines"

    return (
        "Analyze the following symbol for trading blockers:\n\n"
        f"Symbol: {symbol}\n"
        f"Company: {company_name}\n"
        f"Last Price: INR {last_price:.2f}\n"
        f"ATR-14: INR {atr:.2f}\n\n"
        f"Recent Headlines:\n{headlines_text}\n\n"
        "Return a BlockerReport as valid JSON."
        " If no blockers, return empty blockers_found list."
    )
