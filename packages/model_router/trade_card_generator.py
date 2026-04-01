"""Trade card generator — produces TradeCard via LLM."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from packages.contracts.audit_event import AuditEvent
from packages.contracts.candidates import CoreCandidate, SwingCandidate
from packages.contracts.enums import Mode
from packages.contracts.llm import ModelRole
from packages.contracts.portfolio import PortfolioState
from packages.contracts.regime_state import RegimeState
from packages.contracts.trade_card import TradeCard
from services.audit_ledger.ledger import AuditLedger

from .parser import OutputParseError, StructuredOutputParser
from .prompts import trade_card
from .providers.base import AllProvidersFailedError
from .router import ModelRouter

logger = logging.getLogger(__name__)


class TradeCardGenerationError(Exception):
    """Raised when trade card generation fails."""

    def __init__(self, symbol: str, reason: str) -> None:
        self.symbol = symbol
        self.reason = reason
        super().__init__(f"Failed to generate TradeCard for {symbol}: {reason}")


class TradeCardGenerator:
    """Generates TradeCards via LLM for screened candidates."""

    def __init__(
        self,
        router: ModelRouter,
        parser: StructuredOutputParser,
        audit_ledger: AuditLedger,
        mode: Mode = Mode.PAPER,
    ) -> None:
        self._router = router
        self._parser = parser
        self._audit_ledger = audit_ledger
        self._mode = mode

    async def generate(
        self,
        candidate: SwingCandidate | CoreCandidate,
        regime: RegimeState,
        portfolio: PortfolioState,
    ) -> TradeCard:
        """Generate a TradeCard for a candidate.

        Raises TradeCardGenerationError on any failure — trade cards
        require genuine model output, no safe defaults.
        """
        symbol = candidate.symbol
        layer = "swing" if isinstance(candidate, SwingCandidate) else "core"

        # Build prompts
        if isinstance(candidate, SwingCandidate):
            dma_200 = candidate.atr_14  # Simplified — real impl would have this
            dma_50 = candidate.atr_14
            volume_ratio = candidate.volume_ratio
        else:
            dma_200 = candidate.dma_200
            dma_50 = candidate.dma_50
            volume_ratio = candidate.close / candidate.dma_200  # Approximate

        system = trade_card.build_system_prompt()
        prompt = trade_card.build_user_prompt(
            symbol=symbol,
            layer=layer,
            close=candidate.close,
            entry_price_estimate=(
                candidate.entry_price_estimate
                if isinstance(candidate, SwingCandidate)
                else candidate.close
            ),
            stop_price=(
                candidate.stop_price
                if isinstance(candidate, SwingCandidate)
                else candidate.dma_200
            ),
            atr_14=(
                candidate.atr_14
                if isinstance(candidate, SwingCandidate)
                else candidate.close - candidate.dma_50
            ),
            dma_200=dma_200,
            dma_50=dma_50,
            volume_ratio=volume_ratio,
            regime_class=regime.regime_class.value,
            portfolio_equity=portfolio.equity,
            portfolio_open_risk_pct=portfolio.open_risk_pct,
        )

        try:
            response = await self._router.complete(
                role=ModelRole.TRADE_CARD,
                prompt=prompt,
                system=system,
            )
            card = self._parser.parse_trade_card(response.text)
            return card

        except OutputParseError as exc:
            logger.error(
                "Trade card parse failure for %s: %s", symbol, exc
            )
            await self._log_failure(symbol, "parse_failure", str(exc))
            raise TradeCardGenerationError(
                symbol, f"parse failure: {exc}"
            ) from exc

        except AllProvidersFailedError as exc:
            logger.error(
                "All providers failed for trade card of %s: %s", symbol, exc
            )
            await self._log_failure(symbol, "all_providers_failed", str(exc))
            raise TradeCardGenerationError(
                symbol, f"all providers failed: {exc}"
            ) from exc

    async def _log_failure(
        self, symbol: str, failure_type: str, detail: str
    ) -> None:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            event_type="trade_card_generation_failure",
            source_service="model-router",
            mode=self._mode,
            payload={
                "symbol": symbol,
                "failure_type": failure_type,
                "detail": detail[:500],
            },
            related_symbol=symbol,
            operator_visible=True,
        )
        await self._audit_ledger.record(event)
