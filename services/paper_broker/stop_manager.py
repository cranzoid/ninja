"""Stop & exit manager — evaluates exit rules for all open positions.

Thin coordinator that calls the exit rule evaluator from Phase 2 and converts
ExitDecisions into OrderIntents. Does NOT duplicate exit logic.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd

from packages.contracts.enums import Mode, PortfolioLayer
from packages.contracts.order_intent import OrderIntent
from packages.contracts.portfolio import Position
from packages.contracts.regime_state import RegimeState
from services.rule_engine.exit_rules import evaluate_exits

logger = logging.getLogger(__name__)


class StopExitManager:
    """
    Evaluates all open positions against exit rules from charter.
    Generates exit OrderIntents when triggers are hit.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        # Per-position state for exit rules
        self._consecutive_days_below_200dma: dict[str, int] = {}
        self._highest_price_since_entry: dict[str, Decimal] = {}
        self._partial_exit_taken: dict[str, bool] = {}

        self._data_dir = data_dir
        if data_dir:
            self._load_state()

    async def evaluate_all_positions(
        self,
        positions: list[Position],
        featured_data: dict[str, pd.DataFrame],
        current_date: date,
        regime: RegimeState,
        mode: Mode = Mode.PAPER,
    ) -> list[OrderIntent]:
        """
        Returns exit OrderIntents for positions that trigger exit rules.
        Uses the exit rule evaluator from services/rule_engine/exit_rules.py.
        """
        # Update per-position tracking state
        self._update_tracking_state(positions, featured_data, current_date)

        # Delegate to the Phase 2 exit evaluator
        decisions = evaluate_exits(positions, featured_data, regime, mode)

        exit_intents: list[OrderIntent] = []
        for decision in decisions:
            if decision.decision == "hold":
                continue

            # Check if partial exit already taken for this symbol
            if (
                decision.decision == "exit_partial"
                and self._partial_exit_taken.get(decision.symbol, False)
            ):
                logger.info(
                    "Skipping duplicate partial exit for %s", decision.symbol
                )
                continue

            if decision.order_intent is not None:
                exit_intents.append(decision.order_intent)

                # Track partial exit
                if decision.decision == "exit_partial":
                    self._partial_exit_taken[decision.symbol] = True

        if self._data_dir:
            self._save_state()

        return exit_intents

    def _update_tracking_state(
        self,
        positions: list[Position],
        featured_data: dict[str, pd.DataFrame],
        current_date: date,
    ) -> None:
        """Update per-position tracking state needed for exit rules."""
        current_symbols = {p.symbol for p in positions}

        # Clean up state for closed positions
        for sym in list(self._consecutive_days_below_200dma.keys()):
            if sym not in current_symbols:
                del self._consecutive_days_below_200dma[sym]
        for sym in list(self._highest_price_since_entry.keys()):
            if sym not in current_symbols:
                del self._highest_price_since_entry[sym]
        for sym in list(self._partial_exit_taken.keys()):
            if sym not in current_symbols:
                del self._partial_exit_taken[sym]

        for pos in positions:
            symbol = pos.symbol
            df = featured_data.get(symbol)

            # Track highest price since entry
            if symbol not in self._highest_price_since_entry:
                self._highest_price_since_entry[symbol] = pos.entry_price
            if pos.current_price > self._highest_price_since_entry[symbol]:
                self._highest_price_since_entry[symbol] = pos.current_price

            # Track consecutive days below 200-DMA (for core positions)
            if pos.layer == PortfolioLayer.CORE and df is not None and not df.empty:
                latest = df.iloc[-1]
                dma_200 = latest.get("dma_200")
                if pd.notna(dma_200):
                    close = float(latest["close"])
                    if close < float(dma_200):
                        self._consecutive_days_below_200dma[symbol] = (
                            self._consecutive_days_below_200dma.get(symbol, 0) + 1
                        )
                    else:
                        self._consecutive_days_below_200dma[symbol] = 0

            # Initialize partial exit tracking
            if symbol not in self._partial_exit_taken:
                self._partial_exit_taken[symbol] = False

    def _save_state(self) -> None:
        """Persist stop manager state."""
        if not self._data_dir:
            return
        self._data_dir.mkdir(parents=True, exist_ok=True)
        state = {
            "consecutive_days_below_200dma": self._consecutive_days_below_200dma,
            "highest_price_since_entry": {
                k: str(v) for k, v in self._highest_price_since_entry.items()
            },
            "partial_exit_taken": self._partial_exit_taken,
        }
        path = self._data_dir / "stop_manager_state.json"
        path.write_text(json.dumps(state, indent=2))

    def _load_state(self) -> None:
        """Load persisted stop manager state."""
        if not self._data_dir:
            return
        path = self._data_dir / "stop_manager_state.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            self._consecutive_days_below_200dma = data.get(
                "consecutive_days_below_200dma", {}
            )
            self._highest_price_since_entry = {
                k: Decimal(v)
                for k, v in data.get("highest_price_since_entry", {}).items()
            }
            self._partial_exit_taken = data.get("partial_exit_taken", {})
        except Exception:
            logger.exception("Failed to load stop manager state")
