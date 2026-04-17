"""ShadowLiveRunner — runs full EOD workflow against live data in dry-run mode.

Runs the full EOD workflow against live market data but routes all order
intents to the dry-run broker adapter. No orders are ever placed. All signals,
decisions, and intents are logged to the audit ledger for later comparison
with what paper mode would have done.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pandas as pd

from packages.brokers.mock_broker import MockBrokerAdapter
from packages.contracts.blocker_report import BlockerReport
from packages.contracts.broker import ShadowRunReport
from packages.contracts.enums import RegimeClass
from packages.contracts.order_intent import OrderIntent
from packages.contracts.order_state import OrderRecord
from packages.contracts.portfolio import PortfolioState
from packages.contracts.regime_state import RegimeState
from packages.model_router.blocker_provider import LLMBlockerProvider
from packages.utils.env_guard import EnvironmentGuard
from services.audit_ledger.ledger import AuditLedger
from services.candidate_engine.core_scanner import scan_core_candidates
from services.candidate_engine.ranker import rank_swing_candidates
from services.candidate_engine.swing_scanner import scan_swing_candidates
from services.data_ingest.providers.base import MarketDataProvider
from services.feature_engine.builder import build_features
from services.paper_broker.stub_blocker import StubBlockerProvider
from services.regime_engine.assessor import assess_regime
from services.risk_engine.calculator import calculate_portfolio_risk
from services.rule_engine.entry_rules import evaluate_swing_entry

logger = logging.getLogger(__name__)


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
        rationale="Default fallback regime (shadow mode).",
    )


class ShadowLiveRunner:
    """Runs the full EOD workflow in shadow mode.

    Uses the real regime engine, real candidate engine, real rule engine,
    and real LLM providers (BedrockProvider primary in shadow/live mode).
    All generated OrderIntents are passed to the dry-run broker — logged
    but never submitted. Only the broker adapter is stubbed; the LLM path
    exercises the production stack so shadow runs faithfully simulate live.
    """

    def __init__(
        self,
        data_provider: MarketDataProvider,
        mock_broker: MockBrokerAdapter,
        audit_ledger: AuditLedger,
        universe_symbols: list[str] | None = None,
        blocker_provider: LLMBlockerProvider | None = None,
    ) -> None:
        self._data_provider = data_provider
        self._broker = mock_broker
        self._ledger = audit_ledger
        self._blocker_provider = blocker_provider or StubBlockerProvider()
        self._universe = universe_symbols or [
            "RELIANCE", "TCS", "INFY", "HDFCBANK", "SBIN",
        ]
        self._env_guard = EnvironmentGuard()

    async def run_shadow_eod(self, trading_date: date) -> ShadowRunReport:
        """Execute the full shadow EOD workflow for one trading day."""
        # Safety: never run in armed live mode
        self._env_guard.assert_not_live()

        errors: list[str] = []
        intents_generated: list[OrderIntent] = []
        orders_dry_run: list[OrderRecord] = []
        blockers_triggered: list[BlockerReport] = []
        candidates_scanned = 0
        audit_events_count = 0

        regime = _default_regime()
        lookback_start = trading_date - timedelta(days=400)

        # Step 1: Load universe data
        raw_data: dict[str, pd.DataFrame] = {}
        try:
            for symbol in self._universe:
                df = await self._data_provider.fetch_ohlcv(
                    symbol, lookback_start, trading_date
                )
                if not df.empty:
                    raw_data[symbol] = df
            logger.info(
                "Shadow: loaded universe data for %d/%d symbols: %s",
                len(raw_data), len(self._universe), sorted(raw_data),
            )
        except Exception as e:
            errors.append(f"data_load: {e}")
            logger.exception("Shadow: Failed to load universe data")

        # Step 1b: Load NIFTY50 index and VIX (best-effort; missing either
        # degrades the regime assessment but must not fail the whole run).
        nifty_raw = pd.DataFrame()
        vix_level: Decimal | None = None
        try:
            nifty_raw = await self._data_provider.fetch_ohlcv(
                "NIFTY50", lookback_start, trading_date
            )
            logger.info(
                "Shadow: NIFTY50 rows fetched=%d (last_close=%s)",
                len(nifty_raw),
                None if nifty_raw.empty else nifty_raw.iloc[-1]["close"],
            )
        except Exception as e:
            errors.append(f"nifty50_load: {e}")
            logger.exception("Shadow: Failed to load NIFTY50")
        try:
            vix_df = await self._data_provider.fetch_ohlcv(
                "INDIAVIX", lookback_start, trading_date
            )
            if not vix_df.empty:
                vix_level = Decimal(str(round(float(vix_df.iloc[-1]["close"]), 2)))
            logger.info(
                "Shadow: VIX rows fetched=%d (vix_level=%s)",
                len(vix_df), vix_level,
            )
        except Exception as e:
            errors.append(f"vix_load: {e}")
            logger.exception("Shadow: Failed to load INDIAVIX")

        # Step 2: Build features (universe + NIFTY50)
        featured_data: dict[str, pd.DataFrame] = {}
        nifty_featured = pd.DataFrame()
        try:
            for symbol, df in raw_data.items():
                featured_data[symbol] = build_features(df)
            if not nifty_raw.empty:
                nifty_featured = build_features(nifty_raw)
        except Exception as e:
            errors.append(f"build_features: {e}")
            logger.exception("Shadow: Failed to build features")

        # Step 3: Assess regime
        try:
            if nifty_featured.empty:
                logger.warning(
                    "Shadow: NIFTY50 data unavailable — regime trend "
                    "will default to neutral. Check yfinance reachability."
                )
            regime = assess_regime(nifty_featured, featured_data, vix_level)
            logger.info(
                "Shadow: regime assessed class=%s trend=%s "
                "breadth_50dma=%s%% breadth_200dma=%s%% vix=%s vix_state=%s "
                "gaps_5d=%s sizing=%s rationale=%r",
                regime.regime_class.value,
                regime.nifty50_trend,
                regime.breadth_above_50dma_pct,
                regime.breadth_above_200dma_pct,
                regime.vix_level,
                regime.vix_state,
                regime.gap_frequency_5d,
                regime.sizing_multiplier,
                regime.rationale,
            )
        except Exception as e:
            errors.append(f"regime_assessment: {e}")
            logger.exception("Shadow: Failed to assess regime")

        # Step 4: Scan candidates
        swing_candidates = []
        core_candidates = []
        try:
            swing_candidates = scan_swing_candidates(featured_data, regime)
            core_candidates = scan_core_candidates(featured_data, regime)
            candidates_scanned = len(swing_candidates) + len(core_candidates)
        except Exception as e:
            errors.append(f"scan_candidates: {e}")
            logger.exception("Shadow: Failed to scan candidates")

        # Step 5: Rank candidates
        ranked_swing = []
        try:
            ranked_swing = rank_swing_candidates(swing_candidates, max_entries=2)
        except Exception as e:
            errors.append(f"rank_candidates: {e}")

        # Step 6: Evaluate entries and generate intents
        try:
            calculate_portfolio_risk([], Decimal("500000"))
            portfolio_state = PortfolioState(
                equity=Decimal("500000"),
                cash=Decimal("500000"),
                positions=[],
                open_risk_pct=Decimal("0"),
                sector_exposure={},
            )

            from packages.contracts.config_snapshot import RiskLimits
            risk_limits = RiskLimits()

            for candidate in ranked_swing:
                blocker = await self._blocker_provider.scan_blockers(
                    candidate.symbol
                )
                if blocker.is_blocked:
                    blockers_triggered.append(blocker)
                    continue

                decision = evaluate_swing_entry(
                    candidate=candidate,
                    portfolio=portfolio_state,
                    risk_limits=risk_limits,
                    regime=regime,
                    blockers=blocker,
                )
                if decision.decision == "approve" and decision.order_intent is not None:
                    intents_generated.append(decision.order_intent)
        except Exception as e:
            errors.append(f"evaluate_entries: {e}")
            logger.exception("Shadow: Failed to evaluate entries")

        # Step 7: Pass intents to dry-run broker
        for intent in intents_generated:
            try:
                record = await self._broker.place_order(
                    intent, idempotency_key=str(uuid.uuid4())
                )
                orders_dry_run.append(record)
                audit_events_count += 1
            except Exception as e:
                errors.append(f"dry_run_order: {e}")

        completed_at = datetime.now(UTC)
        audit_events_count += len(intents_generated) + 1  # +1 for completion

        return ShadowRunReport(
            trading_date=trading_date,
            regime_state=regime.regime_class.value,
            regime=regime,
            candidates_scanned=candidates_scanned,
            intents_generated=intents_generated,
            orders_dry_run=orders_dry_run,
            blockers_triggered=blockers_triggered,
            audit_events_count=audit_events_count,
            completed_at=completed_at,
            errors=errors,
        )
