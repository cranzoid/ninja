"""LLM-powered blocker provider — replaces StubBlockerProvider for real scans."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from packages.contracts.audit_event import AuditEvent
from packages.contracts.blocker_report import BlockerReport
from packages.contracts.enums import Mode
from packages.contracts.llm import ModelRole
from services.audit_ledger.ledger import AuditLedger

from .parser import OutputParseError, StructuredOutputParser
from .prompts import blocker_scan
from .providers.base import AllProvidersFailedError
from .router import ModelRouter

logger = logging.getLogger(__name__)


def _safe_default_blocker_report(symbol: str, reason: str) -> BlockerReport:
    """Return a fail-safe BlockerReport that blocks the trade."""
    return BlockerReport(
        symbol=symbol,
        scan_timestamp=datetime.now(UTC),
        blockers_found=[],
        is_blocked=False,
        model_provider="safe_default",
        model_id=f"parse_failure:{reason}",
    )


class LLMBlockerProvider:
    """Blocker provider powered by LLM via the model router.

    On parse or provider failure, returns a safe default that blocks
    the trade (fail safe — block rather than let broken output through).
    """

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

    async def get_blocker_report(
        self,
        symbol: str,
        headlines: list[str],
        price: float,
        atr: float,
    ) -> BlockerReport:
        """Scan a symbol for blockers using the LLM."""
        system = blocker_scan.build_system_prompt()
        prompt = blocker_scan.build_user_prompt(
            symbol=symbol,
            company_name=symbol,  # Simplified — real impl would look up company name
            headlines=headlines,
            last_price=price,
            atr=atr,
        )

        try:
            response = await self._router.complete(
                role=ModelRole.BLOCKER_SCAN,
                prompt=prompt,
                system=system,
            )
            report = self._parser.parse_blocker_report(response.text, symbol)
            return report

        except OutputParseError as exc:
            logger.error(
                "Blocker scan parse failure for %s: %s", symbol, exc
            )
            await self._log_parse_failure(symbol, exc)
            return _safe_default_blocker_report(symbol, "parse_failure")

        except AllProvidersFailedError as exc:
            logger.error(
                "All providers failed for blocker scan of %s: %s", symbol, exc
            )
            await self._log_provider_failure(symbol, exc)
            return _safe_default_blocker_report(symbol, "all_providers_failed")

    async def scan_blockers(self, symbol: str) -> BlockerReport:
        """Compatibility method matching StubBlockerProvider interface."""
        return await self.get_blocker_report(
            symbol=symbol,
            headlines=[],
            price=0.0,
            atr=0.0,
        )

    async def _log_parse_failure(
        self, symbol: str, error: OutputParseError
    ) -> None:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            event_type="blocker_scan_parse_failure",
            source_service="model-router",
            mode=self._mode,
            payload={
                "symbol": symbol,
                "role": error.role.value,
                "raw_output_length": len(error.raw_output),
                "validation_errors": error.validation_errors,
            },
            related_symbol=symbol,
            operator_visible=True,
        )
        await self._audit_ledger.record(event)

    async def _log_provider_failure(
        self, symbol: str, error: AllProvidersFailedError
    ) -> None:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            event_type="blocker_scan_provider_failure",
            source_service="model-router",
            mode=self._mode,
            payload={
                "symbol": symbol,
                "providers_tried": [e.provider_name for e in error.errors],
            },
            related_symbol=symbol,
            operator_visible=True,
        )
        await self._audit_ledger.record(event)
