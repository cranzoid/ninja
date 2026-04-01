"""Phase 5 tests — StructuredOutputParser."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.contracts.blocker_report import BlockerReport
from packages.contracts.llm import ExplanationOutput, ModelRole
from packages.contracts.trade_card import TradeCard
from packages.model_router.parser import OutputParseError, StructuredOutputParser


@pytest.fixture
def parser() -> StructuredOutputParser:
    return StructuredOutputParser()


def _valid_blocker_json(symbol: str = "RELIANCE") -> str:
    return json.dumps(
        {
            "symbol": symbol,
            "scan_timestamp": datetime.now(UTC).isoformat(),
            "blockers_found": [],
            "is_blocked": False,
            "model_provider": "test",
            "model_id": "test-v1",
        }
    )


def _valid_trade_card_json() -> str:
    return json.dumps(
        {
            "symbol": "RELIANCE",
            "layer": "swing",
            "direction": "long",
            "thesis_summary": "Breakout on elevated volume.",
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
            "model_provider": "test",
            "model_id": "test-v1",
            "confidence_tag": "high",
        }
    )


def _valid_explanation_json() -> str:
    return json.dumps(
        {
            "plain_language": "Entry approved based on breakout conditions.",
            "confidence": "0.85",
            "key_factors": ["Volume confirmation", "Green regime"],
        }
    )


class TestBlockerReportParsing:
    def test_valid_json(self, parser: StructuredOutputParser) -> None:
        raw = _valid_blocker_json()
        result = parser.parse_blocker_report(raw, "RELIANCE")
        assert isinstance(result, BlockerReport)
        assert result.symbol == "RELIANCE"
        assert result.is_blocked is False

    def test_json_in_markdown_fences(
        self, parser: StructuredOutputParser
    ) -> None:
        raw = f"```json\n{_valid_blocker_json()}\n```"
        result = parser.parse_blocker_report(raw, "RELIANCE")
        assert isinstance(result, BlockerReport)
        assert result.symbol == "RELIANCE"

    def test_json_in_plain_fences(
        self, parser: StructuredOutputParser
    ) -> None:
        raw = f"```\n{_valid_blocker_json()}\n```"
        result = parser.parse_blocker_report(raw, "RELIANCE")
        assert isinstance(result, BlockerReport)

    def test_invalid_json_raises_error(
        self, parser: StructuredOutputParser
    ) -> None:
        with pytest.raises(OutputParseError) as exc_info:
            parser.parse_blocker_report("not json at all", "RELIANCE")
        assert exc_info.value.role == ModelRole.BLOCKER_SCAN

    def test_valid_json_fails_pydantic(
        self, parser: StructuredOutputParser
    ) -> None:
        # Missing required fields
        raw = json.dumps({"symbol": "RELIANCE"})
        with pytest.raises(OutputParseError) as exc_info:
            parser.parse_blocker_report(raw, "RELIANCE")
        assert len(exc_info.value.validation_errors) > 0

    def test_blocker_with_hard_blocker(
        self, parser: StructuredOutputParser
    ) -> None:
        raw = json.dumps(
            {
                "symbol": "HDFCBANK",
                "scan_timestamp": datetime.now(UTC).isoformat(),
                "blockers_found": [
                    {
                        "category": "earnings_window",
                        "severity": "hard",
                        "reason": "Q4 results in 3 days.",
                        "source_category": "earnings_calendar",
                    }
                ],
                "is_blocked": True,
                "model_provider": "test",
                "model_id": "test-v1",
            }
        )
        result = parser.parse_blocker_report(raw, "HDFCBANK")
        assert result.is_blocked is True
        assert len(result.blockers_found) == 1


class TestTradeCardParsing:
    def test_valid_trade_card(self, parser: StructuredOutputParser) -> None:
        raw = _valid_trade_card_json()
        result = parser.parse_trade_card(raw)
        assert isinstance(result, TradeCard)
        assert result.symbol == "RELIANCE"
        assert result.risk_per_share == Decimal("70.00")

    def test_invalid_trade_card_raises_error(
        self, parser: StructuredOutputParser
    ) -> None:
        raw = json.dumps({"symbol": "RELIANCE"})
        with pytest.raises(OutputParseError) as exc_info:
            parser.parse_trade_card(raw)
        assert exc_info.value.role == ModelRole.TRADE_CARD


class TestExplanationParsing:
    def test_valid_explanation(
        self, parser: StructuredOutputParser
    ) -> None:
        raw = _valid_explanation_json()
        result = parser.parse_explanation(raw)
        assert isinstance(result, ExplanationOutput)
        assert result.confidence == Decimal("0.85")
        assert len(result.key_factors) == 2

    def test_invalid_explanation_raises_error(
        self, parser: StructuredOutputParser
    ) -> None:
        raw = json.dumps({"not": "valid"})
        with pytest.raises(OutputParseError):
            parser.parse_explanation(raw)
