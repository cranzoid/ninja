"""EOD run orchestrator — the daily workflow that ties everything together.

One call per simulated trading day. This is the heartbeat of the paper trading system.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd

from packages.contracts.audit_event import AuditEvent
from packages.contracts.config_snapshot import RiskLimits
from packages.contracts.enums import Mode, RegimeClass
from packages.contracts.eod_report import EODRunReport
from packages.contracts.portfolio import PortfolioState, Position
from packages.contracts.regime_state import RegimeState
from services.audit_ledger.ledger import AuditLedger
from services.audit_ledger.reconciler import LedgerReconciler
from services.candidate_engine.core_scanner import scan_core_candidates
from services.candidate_engine.ranker import rank_swing_candidates
from services.candidate_engine.swing_scanner import scan_swing_candidates
from services.data_ingest.providers.base import MarketDataProvider
from services.feature_engine.builder import build_features
from services.regime_engine.assessor import assess_regime
from services.risk_engine.calculator import calculate_portfolio_risk
from services.rule_engine.entry_rules import evaluate_swing_entry

from .broker import PaperBroker
from .stop_manager import StopExitManager
from .stub_blocker import StubBlockerProvider

logger = logging.getLogger(__name__)


class EODOrchestrator:
    """
    Runs the complete end-of-day workflow for one trading day.
    This is the heartbeat of the paper trading system.
    """

    def __init__(
        self,
        data_provider: MarketDataProvider,
        paper_broker: PaperBroker,
        audit_ledger: AuditLedger,
        stop_manager: StopExitManager,
        risk_limits: RiskLimits | None = None,
        universe_symbols: list[str] | None = None,
    ) -> None:
        self._data_provider = data_provider
        self._broker = paper_broker
        self._ledger = audit_ledger
        self._stop_manager = stop_manager
        self._risk_limits = risk_limits or RiskLimits()
        self._blocker_provider = StubBlockerProvider()
        self._reconciler = LedgerReconciler()
        self._universe = universe_symbols or [
            "RELIANCE", "TCS", "INFY", "HDFCBANK", "SBIN",
        ]

    async def run_eod(self, trading_date: date) -> EODRunReport:
        """Execute the full EOD workflow for one trading day."""
        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)
        errors: list[str] = []

        # Counters
        candidates_scanned = 0
        swing_passing = 0
        core_passing = 0
        entries_approved = 0
        entries_rejected = 0
        exits_triggered = 0
        orders_filled = 0

        # Default regime in case assessment fails
        regime = _default_regime()

        # We need a lookback window for features (200-DMA needs ~200 bars)
        from datetime import timedelta

        lookback_start = trading_date - timedelta(days=400)

        # Step 1: Load data
        await self._record_step_event("eod_step_load_data", trading_date, run_id)
        raw_data: dict[str, pd.DataFrame] = {}
        try:
            for symbol in self._universe:
                df = await self._data_provider.fetch_ohlcv(
                    symbol, lookback_start, trading_date
                )
                if not df.empty:
                    raw_data[symbol] = df
        except Exception as e:
            errors.append(f"data_load: {e}")
            logger.exception("Failed to load data")

        # Step 2: Build features
        await self._record_step_event("eod_step_build_features", trading_date, run_id)
        featured_data: dict[str, pd.DataFrame] = {}
        try:
            for symbol, df in raw_data.items():
                featured_data[symbol] = build_features(df)
        except Exception as e:
            errors.append(f"build_features: {e}")
            logger.exception("Failed to build features")

        # Step 3: Assess regime
        await self._record_step_event("eod_step_assess_regime", trading_date, run_id)
        try:
            # Use first symbol with "NIFTY" in name, or first available as proxy
            nifty_data = featured_data.get(
                "NIFTY50",
                next(iter(featured_data.values()), pd.DataFrame()),
            )
            regime = assess_regime(nifty_data, featured_data, None)
        except Exception as e:
            errors.append(f"regime_assessment: {e}")
            logger.exception("Failed to assess regime")

        # Step 4: Simulate fills from previous day's submitted orders
        await self._record_step_event("eod_step_simulate_fills", trading_date, run_id)
        try:
            fill_events = await self._broker.simulate_fills(raw_data, trading_date)
            orders_filled = len(fill_events)
            await self._ledger.record_batch(fill_events)
        except Exception as e:
            errors.append(f"simulate_fills: {e}")
            logger.exception("Failed to simulate fills")

        # Update current prices on positions
        try:
            self._broker.update_current_prices(raw_data, trading_date)
        except Exception as e:
            errors.append(f"update_prices: {e}")

        # Step 5: Evaluate exits
        await self._record_step_event("eod_step_evaluate_exits", trading_date, run_id)
        exit_intents = []
        try:
            positions = await self._broker.get_positions()
            exit_intents = await self._stop_manager.evaluate_all_positions(
                positions=positions,
                featured_data=featured_data,
                current_date=trading_date,
                regime=regime,
            )
            exits_triggered = len(exit_intents)
        except Exception as e:
            errors.append(f"evaluate_exits: {e}")
            logger.exception("Failed to evaluate exits")

        # Step 6: Submit exit orders
        await self._record_step_event("eod_step_submit_exits", trading_date, run_id)
        try:
            for intent in exit_intents:
                record = await self._broker.place_order(intent)
                await self._ledger.record(
                    _make_event(
                        "exit_order_submitted",
                        trading_date,
                        intent.symbol,
                        intent.intent_id,
                        {"order_id": record.order_id, "reason": "exit_rule_triggered"},
                    )
                )
        except Exception as e:
            errors.append(f"submit_exits: {e}")
            logger.exception("Failed to submit exit orders")

        # Step 7: Calculate risk
        await self._record_step_event("eod_step_calculate_risk", trading_date, run_id)
        positions = await self._broker.get_positions()
        try:
            portfolio_risk = calculate_portfolio_risk(
                positions, self._broker.cash + _positions_value(positions),
                self._risk_limits,
            )
        except Exception as e:
            errors.append(f"calculate_risk: {e}")
            logger.exception("Failed to calculate risk")
            portfolio_risk = calculate_portfolio_risk([], Decimal("0"))

        # Step 8: Scan candidates
        await self._record_step_event("eod_step_scan_candidates", trading_date, run_id)
        swing_candidates = []
        core_candidates = []
        try:
            swing_candidates = scan_swing_candidates(featured_data, regime)
            core_candidates = scan_core_candidates(featured_data, regime)
            candidates_scanned = len(swing_candidates) + len(core_candidates)
            swing_passing = sum(
                1 for c in swing_candidates if c.passes_all_entry_conditions
            )
            core_passing = sum(
                1 for c in core_candidates if c.passes_entry_conditions
            )
        except Exception as e:
            errors.append(f"scan_candidates: {e}")
            logger.exception("Failed to scan candidates")

        # Step 9: Rank candidates
        ranked_swing = []
        try:
            ranked_swing = rank_swing_candidates(
                swing_candidates,
                max_entries=self._risk_limits.max_new_swing_entries_per_day,
            )
        except Exception as e:
            errors.append(f"rank_candidates: {e}")

        # Step 10: Evaluate entries
        await self._record_step_event(
            "eod_step_evaluate_entries", trading_date, run_id
        )
        entry_intents = []
        try:
            equity = self._broker.cash + _positions_value(positions)
            portfolio_state = PortfolioState(
                equity=equity,
                cash=self._broker.cash,
                positions=positions,
                open_risk_pct=portfolio_risk.open_risk_pct,
                sector_exposure=portfolio_risk.sector_exposure,
            )

            for candidate in ranked_swing:
                blockers = await self._blocker_provider.scan_blockers(
                    candidate.symbol
                )
                decision = evaluate_swing_entry(
                    candidate=candidate,
                    portfolio=portfolio_state,
                    risk_limits=self._risk_limits,
                    regime=regime,
                    blockers=blockers,
                )
                if decision.decision == "approve" and decision.order_intent is not None:
                    entry_intents.append(decision.order_intent)
                    entries_approved += 1

                    await self._ledger.record(
                        _make_event(
                            "order_intent_created",
                            trading_date,
                            candidate.symbol,
                            decision.order_intent.intent_id,
                            {
                                "intent_id": decision.order_intent.intent_id,
                                "side": decision.order_intent.side.value,
                                "quantity": decision.order_intent.quantity,
                            },
                        )
                    )
                else:
                    entries_rejected += 1
        except Exception as e:
            errors.append(f"evaluate_entries: {e}")
            logger.exception("Failed to evaluate entries")

        # Step 11: Submit entry orders (these will fill tomorrow)
        await self._record_step_event(
            "eod_step_submit_entries", trading_date, run_id
        )
        try:
            for intent in entry_intents:
                record = await self._broker.place_order(intent)
                await self._ledger.record(
                    _make_event(
                        "entry_order_submitted",
                        trading_date,
                        intent.symbol,
                        intent.intent_id,
                        {"order_id": record.order_id},
                    )
                )
        except Exception as e:
            errors.append(f"submit_entries: {e}")
            logger.exception("Failed to submit entry orders")

        # Step 12: Reconcile
        await self._record_step_event("eod_step_reconcile", trading_date, run_id)
        try:
            all_orders = await self._broker.get_orders()
            reconciliation = await self._reconciler.reconcile(
                broker_positions=positions,
                broker_orders=all_orders,
                ledger=self._ledger,
                target_date=trading_date,
            )
        except Exception as e:
            errors.append(f"reconcile: {e}")
            logger.exception("Failed to reconcile")
            from packages.contracts.reconciliation import ReconciliationReport

            reconciliation = ReconciliationReport(
                reconciled_at=datetime.now(UTC),
                target_date=trading_date,
                positions_match=False,
                orders_match=False,
                position_mismatches=[f"reconciliation_failed: {e}"],
                order_mismatches=[],
                unmatched_intents=[],
                orphan_fills=[],
                is_clean=False,
            )

        # Step 13: Generate report
        completed_at = datetime.now(UTC)
        report = EODRunReport(
            run_id=run_id,
            trading_date=trading_date,
            mode=Mode.PAPER,
            started_at=started_at,
            completed_at=completed_at,
            regime=regime,
            candidates_scanned=candidates_scanned,
            swing_candidates_passing=swing_passing,
            core_candidates_passing=core_passing,
            entries_approved=entries_approved,
            entries_rejected=entries_rejected,
            exits_triggered=exits_triggered,
            orders_filled=orders_filled,
            portfolio_risk=portfolio_risk,
            reconciliation=reconciliation,
            errors=errors,
            is_successful=len(errors) == 0,
        )

        # Record completion event
        await self._ledger.record(
            _make_event(
                "eod_run_completed",
                trading_date,
                None,
                None,
                {
                    "run_id": run_id,
                    "trading_date": trading_date.isoformat(),
                    "is_successful": report.is_successful,
                    "orders_filled": orders_filled,
                    "entries_approved": entries_approved,
                    "exits_triggered": exits_triggered,
                    "errors": errors,
                },
            )
        )

        return report

    async def _record_step_event(
        self, step_name: str, trading_date: date, run_id: str
    ) -> None:
        """Record an audit event for an EOD step."""
        await self._ledger.record(
            _make_event(
                step_name,
                trading_date,
                None,
                None,
                {"run_id": run_id, "trading_date": trading_date.isoformat()},
                operator_visible=False,
            )
        )


def _default_regime() -> RegimeState:
    """Fallback regime if assessment fails."""
    return RegimeState(
        assessed_at=datetime.now(UTC),
        regime_class=RegimeClass.MIXED,
        nifty50_trend="neutral",
        breadth_above_50dma_pct=Decimal("50.0"),
        breadth_above_200dma_pct=Decimal("50.0"),
        vix_level=None,
        vix_state="normal",
        gap_frequency_5d=Decimal("0"),
        sector_concentration_score=Decimal("0.5"),
        correlation_state="normal",
        sizing_multiplier=Decimal("0.5"),
        rationale="Default fallback regime (assessment failed).",
    )


def _positions_value(positions: list[Position]) -> Decimal:
    """Calculate total market value of positions."""
    total = Decimal("0")
    for p in positions:
        total += p.current_price * p.quantity
    return total


def _make_event(
    event_type: str,
    trading_date: date,
    symbol: str | None,
    intent_id: str | None,
    payload: dict[str, object],
    operator_visible: bool = True,
) -> AuditEvent:
    """Helper to create audit events."""
    return AuditEvent(
        event_id=str(uuid.uuid4()),
        timestamp=datetime.now(UTC),
        event_type=event_type,
        source_service="eod_orchestrator",
        mode=Mode.PAPER,
        payload=payload,
        related_symbol=symbol,
        related_intent_id=intent_id,
        operator_visible=operator_visible,
    )
