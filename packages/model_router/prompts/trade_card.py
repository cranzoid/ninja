"""Prompt templates for the trade card generation model role."""

from __future__ import annotations

import json
from decimal import Decimal

from packages.contracts.trade_card import TradeCard


def build_system_prompt() -> str:
    """Build the system prompt for trade card generation."""
    schema = json.dumps(TradeCard.model_json_schema(), indent=2)
    return (
        "You are a thesis extractor for an Indian equities"
        " trading system.\n\n"
        "Your role is to generate a structured TradeCard"
        " for a candidate that has passed initial"
        " screening.\n\n"
        "CONSTRAINTS (charter rules):\n"
        "- No leverage -- cash equities only\n"
        "- No options or derivatives\n"
        '- No short selling -- direction is always "long"\n'
        "- Swing layer: satellite positions,"
        " stop = 2xATR below entry\n"
        "- Core layer: long-term holds above 200-DMA\n"
        "- risk_per_share MUST equal"
        " entry_price_target minus stop_price\n"
        "- stop_price MUST be strictly below"
        " entry_price_target for long direction\n"
        "- All prices in INR\n\n"
        "OUTPUT RULES:\n"
        "- Output ONLY valid JSON matching the schema below."
        " No other text.\n"
        "- thesis_summary: 1-3 sentences explaining"
        " the trade rationale\n"
        '- confidence_tag: "high", "medium",'
        ' or "low" (or null)\n\n'
        f"OUTPUT SCHEMA:\n{schema}"
    )


def build_user_prompt(
    symbol: str,
    layer: str,
    close: Decimal,
    entry_price_estimate: Decimal,
    stop_price: Decimal,
    atr_14: Decimal,
    dma_200: Decimal,
    dma_50: Decimal,
    volume_ratio: Decimal,
    regime_class: str,
    portfolio_equity: Decimal,
    portfolio_open_risk_pct: Decimal,
) -> str:
    """Build the user prompt for trade card generation."""
    return (
        "Generate a TradeCard for the following candidate:\n\n"
        f"Symbol: {symbol}\n"
        f"Layer: {layer}\n"
        f"Current Close: INR {close}\n"
        f"Entry Price Estimate: INR {entry_price_estimate}\n"
        f"Stop Price: INR {stop_price}\n"
        f"ATR-14: INR {atr_14}\n"
        f"200-DMA: INR {dma_200}\n"
        f"50-DMA: INR {dma_50}\n"
        f"Volume Ratio (20d): {volume_ratio}x\n\n"
        f"Market Regime: {regime_class}\n"
        f"Portfolio Equity: INR {portfolio_equity}\n"
        f"Portfolio Open Risk: {portfolio_open_risk_pct}%\n\n"
        "Generate a TradeCard as valid JSON."
        " Ensure risk_per_share ="
        " entry_price_target - stop_price."
    )
