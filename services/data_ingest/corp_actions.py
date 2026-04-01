"""Corporate action provider — interface and fixture implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from packages.contracts.corp_action import CorporateAction


class CorporateActionProvider(ABC):
    """Abstract provider for corporate action data (charter §9)."""

    @abstractmethod
    async def get_actions(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[CorporateAction]:
        """Get corporate actions for a symbol in a date range."""
        ...


class FixtureCorporateActionProvider(CorporateActionProvider):
    """Returns empty lists — stub for Phase 2."""

    async def get_actions(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[CorporateAction]:
        return []
