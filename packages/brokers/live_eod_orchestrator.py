"""Live EOD orchestrator — daily workflow for live trading.

Phase 7: Tiny Live. Same 13-step workflow as paper EODOrchestrator, but:
- Uses ZerodhaAdapter (real broker) instead of PaperBroker
- Enforces dry_run guard at every order step
- Checks EnvironmentGuard: refuses to run if MODE != live OR ARMED_LIVE != true
- Checks OperatorReviewGate: refuses if previous session has unresolved anomalies
- Uses LIVE_V1_RISK_LIMITS from live_config.py
- Runs LiveReconciler.run_post_close() automatically
- Produces LiveRunReport at end of each session
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pandas as pd

from packages.contracts.audit_event import AuditEvent
from packages.contracts.broker import LiveRunReport
from packages.contracts.config_snapshot import RiskLimits
from packages.contracts.enums import Mode, RegimeClass
from packages.contracts.portfolio import PortfolioState, Position
from packages.contracts.regime_state import RegimeState
from packages.utils.env_guard import EnvironmentGuard
from packages.utils.live_config import LIVE_V1_RISK_LIMITS
from services.audit_ledger.ledger import AuditLedger
from services.candidate_engine.ranker import rank_swing_candidates
from services.candidate_engine.swing_scanner import scan_swing_candidates
from services.data_ingest.providers.base import MarketDataProvider
from services.feature_engine.builder import build_features
from services.regime_engine.assessor import assess_regime
from services.risk_engine.calculator import calculate_portfolio_risk
from services.rule_engine.entry_rules import evaluate_swing_entry

from .live_reconciler import LiveReconciler, OperatorReviewGate
from .zerodha import ZerodhaAdapter

logger = logging.getLogger(__name__)


class LiveEODOrchestrator:
    """Live version of EODOrchestrator.

    Same 13-step workflow as paper, but with real broker, tighter risk
    limits, environment guards, and post-close reconciliation.
    """

    def __init__(
        self,
        data_provider: MarketDataProvider,
        broker: ZerodhaAdapter,
        audit_ledger: AuditLedger,
        reconciler: LiveReconciler,
        review_gate: OperatorReviewGate,
        risk_limits: RiskLimits | None = None,
        universe_symbols: list[str] | None = None,
        last_live_report: LiveRunReport | None = None,
    ) -> None:
        self._data_provider = data_provider
        self._broker = broker
        self._ledger = audit_ledger
        self._reconciler = reconciler
        self._review_gate = review_gate
        self._risk_limits = risk_limits or LIVE_V1_RISK_LIMITS
        self._env_guard = EnvironmentGuard()
        self._universe = universe_symbols or [
            "RELIANCE", "TCS", "INFY", "HDFCBANK", "SBIN",
        ]
        self._last_report = last_live_report

    def set_last_report(self, report: LiveRunReport | None) -> None:
        """Update the last report reference (called by AppState)."""
        self._last_report = report

    async def run_eod(self, trading_date: date) -> LiveRunReport:
        """Execute the full live EOD workflow for one trading day."""

        # --- Pre-flight checks ---
        # 1. Environment guard: must be MODE=live AND ARMED_LIVE=true
        mode = self._env_guard.get_mode()
        armed = self._env_guard.is_armed_live()
        if mode != Mode.LIVE:
            raise RuntimeError(
                f"LiveEODOrchestrator requires MODE=live, got MODE={mode.value}"
            )
        if not armed:
            raise RuntimeError(
                "LiveEODOrchestrator requires ARMED_LIVE=true"
            )

        # 2. Operator review gate: no unresolved anomalies from previous session
        if not self._review_gate.can_run_next_session(self._last_report):
            raise RuntimeError(
                "Previous live session has unresolved anomalies. "
                "Operator must review before next session can run."
            )

        run_id = str(uuid.uuid4())
        errors: list[str] = []

        # Capture positions before
        positions_before = await self._broker.get_positions()

        # Lookback window for features
        lookback_start = trading_date - timedelta(days=400)

        # Step 1: Load data
        await self._record_event("live_eod_step_load_data", trading_date, run_id)
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
        await self._record_event("live_eod_step_build_features", trading_date, run_id)
        featured_data: dict[str, pd.DataFrame] = {}
        try:
            for symbol, df in raw_data.items():
                featured_data[symbol] = build_features(df)
        except Exception as e:
            errors.append(f"build_features: {e}")
            logger.exception("Failed to build features")

        # Step 3: Assess regime
        await self._record_event("live_eod_step_assess_regime", trading_date, run_id)
        regime = _default_regime()
        try:
            nifty_data = featured_data.get(
                "NIFTY50",
                next(iter(featured_data.values()), pd.DataFrame()),
            )
            regime = assess_regime(nifty_data, featured_data, None)
        except Exception as e:
            errors.append(f"regime_assessment: {e}")
            logger.exception("Failed to assess regime")

        # Step 4: Get current positions and orders from broker
        await self._record_event("live_eod_step_get_broker_state", trading_date, run_id)
        positions = await self._broker.get_positions()
        await self._broker.get_orders(since=trading_date)

        # Step 5: Calculate risk
        await self._record_event("live_eod_step_calculate_risk", trading_date, run_id)
        equity = _positions_value(positions)
        try:
            portfolio_risk = calculate_portfolio_risk(
                positions, equity, self._risk_limits
            )
        except Exception as e:
            errors.append(f"calculate_risk: {e}")
            logger.exception("Failed to calculate risk")
            portfolio_risk = calculate_portfolio_risk([], Decimal("0"))

        # Step 6: Scan candidates
        await self._record_event("live_eod_step_scan_candidates", trading_date, run_id)
        swing_candidates = []
        try:
            swing_candidates = scan_swing_candidates(featured_data, regime)
        except Exception as e:
            errors.append(f"scan_candidates: {e}")
            logger.exception("Failed to scan candidates")

        # Step 7: Rank candidates
        ranked_swing = []
        try:
            ranked_swing = rank_swing_candidates(
                swing_candidates,
                max_entries=self._risk_limits.max_new_swing_entries_per_day,
            )
        except Exception as e:
            errors.append(f"rank_candidates: {e}")

        # Step 8: Evaluate entries
        await self._record_event("live_eod_step_evaluate_entries", trading_date, run_id)
        entry_intents = []
        try:
            portfolio_state = PortfolioState(
                equity=equity,
                cash=Decimal("0"),
                positions=positions,
                open_risk_pct=portfolio_risk.open_risk_pct,
                sector_exposure=portfolio_risk.sector_exposure,
            )

            from services.paper_broker.stub_blocker import StubBlockerProvider
            blocker_provider = StubBlockerProvider()

            for candidate in ranked_swing:
                blockers = await blocker_provider.scan_blockers(candidate.symbol)
                decision = evaluate_swing_entry(
                    candidate=candidate,
                    portfolio=portfolio_state,
                    risk_limits=self._risk_limits,
                    regime=regime,
                    blockers=blockers,
                )
                if decision.decision == "approve" and decision.order_intent is not None:
                    entry_intents.append(decision.order_intent)
        except Exception as e:
            errors.append(f"evaluate_entries: {e}")
            logger.exception("Failed to evaluate entries")

        # Step 9: Submit entry orders via broker
        await self._record_event("live_eod_step_submit_entries", trading_date, run_id)
        submitted_orders: list[object] = []
        try:
            for intent in entry_intents:
                idem_key = (
                    f"live_{trading_date.isoformat()}"
                    f"_{intent.symbol}_{intent.intent_id}"
                )
                record = await self._broker.place_order(intent, idem_key)
                submitted_orders.append(record)
                await self._ledger.record(
                    _make_event(
                        "live_entry_order_submitted",
                        trading_date,
                        intent.symbol,
                        intent.intent_id,
                        {"order_id": record.order_id},
                    )
                )
        except Exception as e:
            errors.append(f"submit_entries: {e}")
            logger.exception("Failed to submit entry orders")

        # Step 10: Get final broker state after submissions
        await self._record_event("live_eod_step_final_state", trading_date, run_id)
        positions_after = await self._broker.get_positions()
        all_orders = await self._broker.get_orders(since=trading_date)

        # Step 11: Run post-close reconciliation
        await self._record_event("live_eod_step_reconcile", trading_date, run_id)
        try:
            report = await self._reconciler.run_post_close(
                broker_orders=all_orders,
                broker_positions=positions_after,
                ledger=self._ledger,
                trading_date=trading_date,
                positions_before=positions_before,
                risk_utilization=portfolio_risk,
            )
        except Exception as e:
            errors.append(f"reconcile: {e}")
            logger.exception("Failed to reconcile")
            # Create a minimal report on reconciliation failure
            from packages.contracts.reconciliation import ReconciliationReport
            report = LiveRunReport(
                trading_date=trading_date,
                mode=Mode.LIVE.value,
                orders_submitted=all_orders,
                orders_filled=[],
                orders_cancelled=[],
                positions_before=positions_before,
                positions_after=positions_after,
                reconciliation_result=ReconciliationReport(
                    reconciled_at=datetime.now(UTC),
                    target_date=trading_date,
                    positions_match=False,
                    orders_match=False,
                    position_mismatches=[f"reconciliation_failed: {e}"],
                    order_mismatches=[],
                    unmatched_intents=[],
                    orphan_fills=[],
                    is_clean=False,
                ),
                risk_utilization=portfolio_risk,
                anomalies=[f"reconciliation_failed: {e}"],
                generated_at=datetime.now(UTC),
            )

        # Add any run errors as anomalies
        if errors:
            for err in errors:
                if err not in report.anomalies:
                    report.anomalies.append(err)

        # Step 12: Record completion
        await self._ledger.record(
            _make_event(
                "live_eod_run_completed",
                trading_date,
                None,
                None,
                {
                    "run_id": run_id,
                    "trading_date": trading_date.isoformat(),
                    "anomalies_count": len(report.anomalies),
                    "orders_submitted": len(report.orders_submitted),
                    "orders_filled": len(report.orders_filled),
                    "errors": errors,
                },
            )
        )

        # Update last report reference
        self._last_report = report

        return report

    async def _record_event(
        self, step_name: str, trading_date: date, run_id: str
    ) -> None:
        """Record an audit event for a live EOD step."""
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
        source_service="live_eod_orchestrator",
        mode=Mode.LIVE,
        payload=payload,
        related_symbol=symbol,
        related_intent_id=intent_id,
        operator_visible=operator_visible,
    )
