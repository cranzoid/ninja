"""AppState — singleton service registry for the operator console API.

Holds all initialized service instances for the API lifetime.
Created once at startup via the lifespan event, injected into route handlers.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from packages.brokers.live_eod_orchestrator import LiveEODOrchestrator
from packages.brokers.live_reconciler import LiveReconciler, OperatorReviewGate
from packages.brokers.mock_broker import MockBrokerAdapter
from packages.brokers.shadow_runner import ShadowLiveRunner
from packages.brokers.zerodha import ZerodhaAdapter
from packages.compliance.checks.audit_sink import AuditSinkCheck
from packages.compliance.checks.base import ComplianceCheck
from packages.compliance.checks.broker_auth import BrokerAuthCheck
from packages.compliance.checks.broker_health import BrokerHealthCheck
from packages.compliance.checks.clock_check import ClockCheck
from packages.compliance.checks.config_checksum import ConfigChecksumCheck
from packages.compliance.checks.env_vars import EnvVarsCheck
from packages.compliance.checks.kill_switch import KillSwitchCheck
from packages.compliance.checks.mode_flag import ModeFlagCheck
from packages.compliance.gate import ComplianceGate
from packages.contracts.audit_event import AuditEvent
from packages.contracts.broker import BrokerConfig, LiveRunReport, ShadowRunReport
from packages.contracts.compliance import ComplianceContext, ComplianceReport
from packages.contracts.config_snapshot import ConfigSnapshot, RiskLimits
from packages.contracts.enums import (
    ExecutionTiming,
    Mode,
    OrderSide,
    OrderStatus,
    OrderType,
    OverrideAction,
    RegimeClass,
)
from packages.contracts.eod_report import EODRunReport
from packages.contracts.llm import (
    ModelRole,
    ModelRouterConfig,
    ProviderConfig,
    RoleRouting,
)
from packages.contracts.order_intent import OrderIntent
from packages.contracts.order_state import OrderRecord
from packages.contracts.portfolio import Position
from packages.contracts.regime_state import RegimeState
from packages.contracts.simulation import SimulationSummary
from packages.model_router.blocker_provider import LLMBlockerProvider
from packages.model_router.explanation_generator import ExplanationGenerator
from packages.model_router.parser import StructuredOutputParser
from packages.model_router.providers.base import LLMProvider
from packages.model_router.providers.fixture import FixtureProvider
from packages.model_router.router import ModelRouter
from packages.model_router.telemetry import ModelTelemetry
from packages.model_router.trade_card_generator import TradeCardGenerator
from services.audit_ledger.ledger import AuditLedger
from services.audit_ledger.reconciler import LedgerReconciler
from services.data_ingest.providers.fixture_provider import FixtureMarketDataProvider
from services.data_ingest.providers.yfinance_provider import YFinanceMarketDataProvider
from services.paper_broker.broker import PaperBroker
from services.paper_broker.eod_orchestrator import EODOrchestrator
from services.paper_broker.simulation_runner import PaperSimulationRunner
from services.paper_broker.stop_manager import StopExitManager


def _make_config_checksum(risk_limits: RiskLimits) -> str:
    raw = risk_limits.model_dump_json()
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def make_default_config(
    mode: Mode = Mode.PAPER,
    armed_live: bool = False,
) -> ConfigSnapshot:
    """Create a default ConfigSnapshot for startup."""
    risk_limits = RiskLimits()
    return ConfigSnapshot(
        snapshot_id=str(uuid.uuid4()),
        captured_at=datetime.now(UTC),
        mode=mode,
        armed_live=armed_live,
        risk_limits=risk_limits,
        regime_state=RegimeClass.MIXED,
        universe_size=5,
        active_blockers_count=0,
        config_checksum=_make_config_checksum(risk_limits),
    )


def _default_regime() -> RegimeState:
    """Fallback regime when no EOD runs have completed."""
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
        rationale="Default regime — no EOD runs completed yet.",
    )


class AppState:
    """
    Holds all initialized service instances for the API lifetime.

    Created once at startup, injected into route handlers via dependency injection.
    Also holds extra mutable state (frozen symbols, override history, stop overrides,
    run history) that lives above the individual service layer.
    """

    def __init__(
        self,
        paper_broker: PaperBroker,
        audit_ledger: AuditLedger,
        stop_manager: StopExitManager,
        orchestrator: EODOrchestrator,
        simulation_runner: PaperSimulationRunner,
        reconciler: LedgerReconciler,
        data_provider: FixtureMarketDataProvider,
        config: ConfigSnapshot,
        model_router: ModelRouter,
        blocker_provider: LLMBlockerProvider,
        trade_card_generator: TradeCardGenerator,
        explanation_generator: ExplanationGenerator,
        model_telemetry: ModelTelemetry,
        # Phase 6 additions
        compliance_gate: ComplianceGate | None = None,
        mock_broker: MockBrokerAdapter | None = None,
        shadow_runner: ShadowLiveRunner | None = None,
        broker_config: BrokerConfig | None = None,
    ) -> None:
        self.paper_broker = paper_broker
        self.audit_ledger = audit_ledger
        self.stop_manager = stop_manager
        self.orchestrator = orchestrator
        self.simulation_runner = simulation_runner
        self.reconciler = reconciler
        self.data_provider = data_provider
        self.config = config
        self.model_router = model_router
        self.blocker_provider = blocker_provider
        self.trade_card_generator = trade_card_generator
        self.explanation_generator = explanation_generator
        self.model_telemetry = model_telemetry

        # Phase 6 additions
        self.compliance_gate = compliance_gate
        self.mock_broker = mock_broker
        self.shadow_runner = shadow_runner
        self.broker_config = broker_config

        # Phase 7 additions
        self.live_orchestrator: LiveEODOrchestrator | None = None
        self.review_gate: OperatorReviewGate | None = None
        self.zerodha_adapter: ZerodhaAdapter | None = None

        # Mutable operational state
        self.frozen_symbols: set[str] = set()
        self.stop_overrides: dict[str, Decimal] = {}
        self.eod_run_history: list[EODRunReport] = []
        self.simulation_history: list[SimulationSummary] = []
        self.shadow_run_history: list[ShadowRunReport] = []
        self.live_run_history: list[LiveRunReport] = []
        self.alert_acknowledgments: dict[str, datetime] = {}
        self.config_history: list[ConfigSnapshot] = [config]
        # Latest regime snapshot, written back by shadow/EOD runs so
        # /api/regime/current reflects real assessments rather than the
        # startup default.
        self.latest_regime_state: RegimeState | None = None

    @classmethod
    async def initialize(
        cls,
        data_dir: Path,
        config: ConfigSnapshot,
    ) -> AppState:
        """Create all service instances and return a ready AppState."""
        from packages.contracts.broker_config import PaperBrokerConfig

        data_dir.mkdir(parents=True, exist_ok=True)

        data_provider = FixtureMarketDataProvider()
        shadow_data_provider: FixtureMarketDataProvider | YFinanceMarketDataProvider = (
            YFinanceMarketDataProvider() if config.mode != Mode.PAPER else data_provider
        )

        broker_config = PaperBrokerConfig(data_dir=data_dir / "broker")
        paper_broker = PaperBroker(broker_config)

        audit_ledger = AuditLedger(data_dir / "audit")
        stop_manager = StopExitManager(data_dir=data_dir / "stops")

        orchestrator = EODOrchestrator(
            data_provider=data_provider,
            paper_broker=paper_broker,
            audit_ledger=audit_ledger,
            stop_manager=stop_manager,
            risk_limits=config.risk_limits,
            universe_symbols=["RELIANCE", "TCS", "INFY", "HDFCBANK", "SBIN"],
        )

        simulation_runner = PaperSimulationRunner(
            orchestrator=orchestrator,
            data_dir=data_dir / "sims",
        )

        reconciler = LedgerReconciler()

        # Phase 5: Model routing — paper mode always uses FixtureProvider
        model_telemetry = ModelTelemetry()
        model_router_config = _build_model_router_config(config.mode)
        providers = _build_providers(config.mode)

        model_router = ModelRouter(
            config=model_router_config,
            providers=providers,
            audit_ledger=audit_ledger,
            telemetry=model_telemetry,
            mode=config.mode,
        )

        parser = StructuredOutputParser()

        blocker_provider = LLMBlockerProvider(
            router=model_router,
            parser=parser,
            audit_ledger=audit_ledger,
            mode=config.mode,
        )

        trade_card_generator = TradeCardGenerator(
            router=model_router,
            parser=parser,
            audit_ledger=audit_ledger,
            mode=config.mode,
        )

        explanation_generator = ExplanationGenerator(
            router=model_router,
            parser=parser,
        )

        # Phase 6: Mock broker, compliance gate, shadow runner
        broker_cfg = BrokerConfig(
            broker_name="mock",
            base_url="http://localhost",
            dry_run=True,
        )
        mock_broker = MockBrokerAdapter(
            config=broker_cfg,
            audit_ledger=audit_ledger,
            mode=config.mode,
        )

        # Phase 7: ZerodhaAdapter created early so compliance gate can use it
        zerodha_config = BrokerConfig(
            broker_name="zerodha",
            base_url=os.environ.get(
                "ZERODHA_BASE_URL", "https://api.kite.trade"),
            timeout_seconds=30,
            max_retries=3,
            dry_run=config.mode != Mode.LIVE or not config.armed_live,
        )
        zerodha_adapter = ZerodhaAdapter(
            config=zerodha_config,
            audit_ledger=audit_ledger,
            mode=config.mode,
            data_dir=data_dir / "broker",
        )

        # In shadow/live mode, compliance broker checks run against ZerodhaAdapter
        # so they reflect real broker reachability, not the mock.
        compliance_broker = (
            zerodha_adapter if config.mode != Mode.PAPER else mock_broker
        )

        # Build compliance checks
        compliance_checks: list[ComplianceCheck] = [
            EnvVarsCheck(),
            KillSwitchCheck(),
            ModeFlagCheck(),
            BrokerAuthCheck(broker_adapter=compliance_broker),
            BrokerHealthCheck(broker_adapter=compliance_broker),
            AuditSinkCheck(audit_ledger=audit_ledger),
            ConfigChecksumCheck(),
            ClockCheck(),
        ]
        compliance_gate = ComplianceGate(
            checks=compliance_checks,
            audit_ledger=audit_ledger,
            mode=config.mode.value,
        )

        shadow_runner = ShadowLiveRunner(
            data_provider=shadow_data_provider,
            mock_broker=mock_broker,
            audit_ledger=audit_ledger,
            blocker_provider=blocker_provider,
        )

        # Phase 7: Live trading infrastructure
        review_gate = OperatorReviewGate(audit_ledger=audit_ledger)
        live_reconciler = LiveReconciler()
        live_orchestrator = LiveEODOrchestrator(
            data_provider=data_provider,
            broker=zerodha_adapter,
            audit_ledger=audit_ledger,
            reconciler=live_reconciler,
            review_gate=review_gate,
        )

        instance = cls(
            paper_broker=paper_broker,
            audit_ledger=audit_ledger,
            stop_manager=stop_manager,
            orchestrator=orchestrator,
            simulation_runner=simulation_runner,
            reconciler=reconciler,
            data_provider=data_provider,
            config=config,
            model_router=model_router,
            blocker_provider=blocker_provider,
            trade_card_generator=trade_card_generator,
            explanation_generator=explanation_generator,
            model_telemetry=model_telemetry,
            compliance_gate=compliance_gate,
            mock_broker=mock_broker,
            shadow_runner=shadow_runner,
            broker_config=broker_cfg,
        )
        instance.live_orchestrator = live_orchestrator
        instance.review_gate = review_gate
        instance.zerodha_adapter = zerodha_adapter

        return instance

    @property
    def active_broker(self) -> MockBrokerAdapter | ZerodhaAdapter | None:
        """Return the live broker in shadow/live mode, mock broker otherwise.

        Used by /api/broker/health and /api/broker/session so those endpoints
        reflect real broker state in shadow/live mode rather than mock data.
        """
        if self.config.mode != Mode.PAPER and self.zerodha_adapter is not None:
            return self.zerodha_adapter
        return self.mock_broker

    # --- Phase 6: Compliance & Shadow ---

    async def run_compliance(self) -> ComplianceReport:
        """Run the full compliance gate and return a report."""
        if self.compliance_gate is None:
            raise RuntimeError("ComplianceGate not initialized")

        env_keys = [
            k for k in os.environ
            if k in {
                "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AWS_REGION",
                "ZERODHA_API_KEY", "ZERODHA_API_SECRET",
                "ZERODHA_REQUEST_TOKEN",
                "STATIC_IP_WHITELIST", "KILL_SWITCH",
                "ARMED_LIVE", "CONFIG_CHECKSUM", "MODE",
                "LIVE_CAPITAL_INR",
            }
        ]

        context = ComplianceContext(
            mode=self.config.mode,
            broker_config=self.broker_config or BrokerConfig(
                broker_name="mock", base_url="http://localhost", dry_run=True,
            ),
            env_vars_present=env_keys,
            static_ip=os.environ.get("STATIC_IP_WHITELIST"),
            armed_live=self.config.armed_live,
            config_checksum=self.config.config_checksum,
        )
        return await self.compliance_gate.run_all(context)

    async def run_live_eod_and_track(
        self, trading_date: date
    ) -> LiveRunReport:
        """Run a live EOD cycle and record the report."""
        if self.live_orchestrator is None:
            raise RuntimeError("LiveEODOrchestrator not initialized")
        report = await self.live_orchestrator.run_eod(trading_date)
        self.live_run_history.append(report)
        return report

    async def get_live_ready(self) -> bool:
        """Check if the system is ready for live trading.

        True only if MODE=live, all blocking compliance checks PASS,
        and no unresolved anomalies from last live run.
        """
        if self.config.mode != Mode.LIVE:
            return False

        try:
            compliance = await self.run_compliance()
            if not compliance.all_blocking_passed:
                return False
        except Exception:
            return False

        if self.live_run_history:
            last = self.live_run_history[-1]
            if self.review_gate and self.review_gate.has_unresolved_anomalies(last):
                return False

        return True

    async def run_shadow_eod_and_track(
        self, trading_date: date
    ) -> ShadowRunReport:
        """Run a shadow EOD cycle and record the report."""
        if self.shadow_runner is None:
            raise RuntimeError("ShadowLiveRunner not initialized")
        report = await self.shadow_runner.run_shadow_eod(trading_date)
        self.shadow_run_history.append(report)
        if report.regime is not None:
            self.latest_regime_state = report.regime
        return report

    # --- Tracked wrappers around service calls ---

    async def run_eod_and_track(self, trading_date: date) -> EODRunReport:
        """Run a single EOD cycle and record the report in history."""
        report = await self.orchestrator.run_eod(trading_date)
        self.eod_run_history.append(report)
        self.latest_regime_state = report.regime
        self._capture_config_snapshot(report)
        return report

    async def run_tracked_simulation(
        self,
        start_date: date,
        end_date: date,
        initial_equity: Decimal,
    ) -> SimulationSummary:
        """Run a simulation and record the summary + daily reports."""
        summary = await self.simulation_runner.run_simulation(
            start_date, end_date, initial_equity
        )
        self.simulation_history.append(summary)
        self.eod_run_history.extend(summary.daily_reports)
        return summary

    def _capture_config_snapshot(self, report: EODRunReport) -> None:
        """Capture a config snapshot after an EOD run."""
        snapshot = ConfigSnapshot(
            snapshot_id=str(uuid.uuid4()),
            captured_at=report.completed_at,
            mode=report.mode,
            armed_live=self.config.armed_live,
            risk_limits=self.config.risk_limits,
            regime_state=report.regime.regime_class,
            universe_size=self.config.universe_size,
            active_blockers_count=0,
            config_checksum=_make_config_checksum(self.config.risk_limits),
        )
        self.config_history.append(snapshot)

    # --- Convenience accessors ---

    def get_latest_regime(self) -> RegimeState:
        """Return the most recent regime assessment, or a safe default.

        Prefers the explicitly-persisted ``latest_regime_state`` written back
        by shadow or EOD runs; falls back to EOD history, then to a safe
        default when the system has never run.
        """
        if self.latest_regime_state is not None:
            return self.latest_regime_state
        if self.eod_run_history:
            return self.eod_run_history[-1].regime
        return _default_regime()

    def get_latest_eod_report(self) -> EODRunReport | None:
        """Return the most recent EOD run report, or None."""
        return self.eod_run_history[-1] if self.eod_run_history else None

    async def get_portfolio_equity(self) -> Decimal:
        """Return total equity: cash + position market value."""
        positions = await self.paper_broker.get_positions()
        pos_value = sum(
            p.current_price * p.quantity for p in positions
        )
        return self.paper_broker.cash + pos_value

    # --- Command execution ---

    async def execute_command(
        self,
        command_type: OverrideAction,
        symbol: str,
        parameters: dict[str, object],
        reason: str,
    ) -> tuple[str, str, OrderRecord | None]:
        """
        Execute an operator override command.

        Returns (status, message, resulting_order).
        """
        now = datetime.now(UTC)
        command_id = str(uuid.uuid4())
        status: str
        message: str
        result_order: OrderRecord | None = None

        try:
            positions = await self.paper_broker.get_positions()
            pos_map = {p.symbol: p for p in positions}

            if command_type == OverrideAction.FREEZE_SYMBOL:
                self.frozen_symbols.add(symbol)
                status, message = (
                    "executed",
                    f"Symbol {symbol} frozen.",
                )

            elif command_type == OverrideAction.CANCEL_ENTRY:
                orders = await self.paper_broker.get_orders(
                    status_filter=OrderStatus.SUBMITTED
                )
                target = next(
                    (
                        o
                        for o in orders
                        if o.intent.symbol == symbol
                        and o.intent.side == OrderSide.BUY
                    ),
                    None,
                )
                if target is None:
                    return (
                        "rejected",
                        f"No submitted BUY order for {symbol}.",
                        None,
                    )
                result_order = await self.paper_broker.cancel_order(
                    target.order_id, reason
                )
                status, message = (
                    "executed",
                    f"Entry order for {symbol} cancelled.",
                )

            elif command_type == OverrideAction.CLOSE_POSITION:
                if symbol not in pos_map:
                    return (
                        "rejected",
                        f"No open position for {symbol}.",
                        None,
                    )
                pos = pos_map[symbol]
                intent = self._build_exit_intent(pos, now)
                result_order = await self.paper_broker.place_order(
                    intent
                )
                status, message = (
                    "executed",
                    f"Close order for {symbol}"
                    f" ({pos.quantity} shares).",
                )

            elif command_type == OverrideAction.REDUCE_SIZE:
                if symbol not in pos_map:
                    return (
                        "rejected",
                        f"No open position for {symbol}.",
                        None,
                    )
                pos = pos_map[symbol]
                new_size_raw = parameters.get("new_size")
                if new_size_raw is None:
                    return (
                        "rejected",
                        "parameters.new_size is required.",
                        None,
                    )
                new_size = int(str(new_size_raw))
                if new_size >= pos.quantity:
                    return (
                        "rejected",
                        f"new_size ({new_size}) must be"
                        f" < current qty ({pos.quantity}).",
                        None,
                    )
                reduce_qty = pos.quantity - new_size
                intent = self._build_partial_exit_intent(
                    pos, reduce_qty, now
                )
                result_order = await self.paper_broker.place_order(
                    intent
                )
                status, message = (
                    "executed",
                    f"Reduced {symbol} by {reduce_qty}"
                    f" shares (new size: {new_size}).",
                )

            elif command_type == OverrideAction.TIGHTEN_STOP:
                if symbol not in pos_map:
                    return (
                        "rejected",
                        f"No open position for {symbol}.",
                        None,
                    )
                pos = pos_map[symbol]
                new_stop_raw = parameters.get("new_stop")
                if new_stop_raw is None:
                    return (
                        "rejected",
                        "parameters.new_stop is required.",
                        None,
                    )
                new_stop = Decimal(str(new_stop_raw))
                current_stop = self.stop_overrides.get(
                    symbol, pos.stop_price
                )
                if new_stop <= current_stop:
                    return (
                        "rejected",
                        f"new_stop ({new_stop}) must be"
                        f" > current stop ({current_stop}).",
                        None,
                    )
                self.stop_overrides[symbol] = new_stop
                status, message = (
                    "executed",
                    f"Stop for {symbol} tightened"
                    f" to {new_stop} (was {current_stop}).",
                )

            else:
                return (
                    "rejected",
                    f"Unsupported command: {command_type}.",
                    None,
                )

        except Exception as exc:
            return "error", str(exc), None

        # Record override audit event
        audit_event = AuditEvent(
            event_id=command_id,
            timestamp=now,
            event_type="override_applied",
            source_service="operator_console",
            mode=self.config.mode,
            payload={
                "command_id": command_id,
                "command_type": command_type.value,
                "symbol": symbol,
                "parameters": {
                    k: str(v) for k, v in parameters.items()
                },
                "reason": reason,
                "status": status,
                "message": message,
            },
            related_symbol=symbol,
            operator_visible=True,
        )
        await self.audit_ledger.record(audit_event)

        return status, message, result_order

    def _build_exit_intent(
        self, pos: Position, now: datetime
    ) -> OrderIntent:
        """Build a full-exit SELL OrderIntent."""
        return OrderIntent(
            intent_id=str(uuid.uuid4()),
            symbol=pos.symbol,
            layer=pos.layer,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=pos.quantity,
            stop_price=pos.stop_price,
            risk_amount=Decimal("0"),
            risk_pct_of_equity=Decimal("0"),
            execution_timing=ExecutionTiming.NEXT_OPEN,
            regime_at_intent=(
                self.get_latest_regime().regime_class
            ),
            created_at=now,
            approved_by="operator_override",
            mode=self.config.mode,
        )

    def _build_partial_exit_intent(
        self, pos: Position, reduce_qty: int, now: datetime
    ) -> OrderIntent:
        """Build a partial-exit SELL OrderIntent."""
        return OrderIntent(
            intent_id=str(uuid.uuid4()),
            symbol=pos.symbol,
            layer=pos.layer,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=reduce_qty,
            stop_price=pos.stop_price,
            risk_amount=Decimal("0"),
            risk_pct_of_equity=Decimal("0"),
            execution_timing=ExecutionTiming.NEXT_OPEN,
            regime_at_intent=(
                self.get_latest_regime().regime_class
            ),
            created_at=now,
            approved_by="operator_override",
            mode=self.config.mode,
        )


def _build_model_router_config(mode: Mode) -> ModelRouterConfig:
    """Build ModelRouterConfig — paper mode forces fixture provider."""
    if mode == Mode.PAPER:
        fixture_cfg = ProviderConfig(
            name="fixture", model_name="fixture-model-v1"
        )
        return ModelRouterConfig(
            providers={"fixture": fixture_cfg},
            role_routing={
                ModelRole.BLOCKER_SCAN: RoleRouting(primary="fixture"),
                ModelRole.TRADE_CARD: RoleRouting(primary="fixture"),
                ModelRole.EXPLANATION: RoleRouting(primary="fixture"),
            },
        )

    # Live/shadow-live: read from environment
    import os

    from packages.contracts.llm import DEFAULT_ROLE_ROUTING

    anthropic_cfg = ProviderConfig(
        name="anthropic",
        model_name=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        timeout_seconds=int(
            os.environ.get("PROVIDER_TIMEOUT_SECONDS", "30")
        ),
        max_retries=int(os.environ.get("PROVIDER_MAX_RETRIES", "2")),
    )
    openai_cfg = ProviderConfig(
        name="openai",
        model_name=os.environ.get("OPENAI_MODEL", "gpt-4o"),
        timeout_seconds=int(
            os.environ.get("PROVIDER_TIMEOUT_SECONDS", "30")
        ),
        max_retries=int(os.environ.get("PROVIDER_MAX_RETRIES", "2")),
    )

    # Bedrock is always included in non-paper mode (charter §7.5: Bedrock-first).
    # Health check will report is_healthy=False if credentials unavailable.
    bedrock_cfg = ProviderConfig(
        name="bedrock",
        model_name=os.environ.get(
            "BEDROCK_MODEL_ID",
            "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        ),
    )

    providers: dict[str, ProviderConfig] = {
        "anthropic": anthropic_cfg,
        "openai": openai_cfg,
        "bedrock": bedrock_cfg,
    }

    default_primary = "bedrock"
    default_fallback_map = {
        ModelRole.BLOCKER_SCAN: "anthropic",
        ModelRole.TRADE_CARD: "anthropic",
        ModelRole.EXPLANATION: "openai",
    }
    default_model_id_map = {
        ModelRole.BLOCKER_SCAN: "global.anthropic.claude-haiku-4-5-20251001-v1:0",
        ModelRole.TRADE_CARD: "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        ModelRole.EXPLANATION: "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    }

    def _get_routing(role: ModelRole, role_env_name: str) -> RoleRouting:
        primary = os.environ.get(
            f"MODEL_ROLE_{role_env_name}_PRIMARY", default_primary
        )
        fallback = os.environ.get(
            f"MODEL_ROLE_{role_env_name}_FALLBACK",
            default_fallback_map.get(role, "anthropic"),
        )
        model_id = (
            DEFAULT_ROLE_ROUTING[role].model_id
            if role in DEFAULT_ROLE_ROUTING
            else default_model_id_map.get(role)
        )
        return RoleRouting(primary=primary, fallback=fallback, model_id=model_id)

    return ModelRouterConfig(
        providers=providers,
        role_routing={
            ModelRole.BLOCKER_SCAN: _get_routing(
                ModelRole.BLOCKER_SCAN, "BLOCKER_SCAN"
            ),
            ModelRole.TRADE_CARD: _get_routing(
                ModelRole.TRADE_CARD, "TRADE_CARD"
            ),
            ModelRole.EXPLANATION: _get_routing(
                ModelRole.EXPLANATION, "EXPLANATION"
            ),
        },
    )


def _build_providers(mode: Mode) -> dict[str, LLMProvider]:
    """Build provider instances based on mode."""
    if mode == Mode.PAPER:
        fixture = FixtureProvider()
        return {"fixture": fixture}

    # Live/shadow-live: create real providers
    import os

    from packages.model_router.providers.anthropic import AnthropicProvider
    from packages.model_router.providers.bedrock import (
        BEDROCK_MODEL_IDS,
        BedrockProvider,
    )
    from packages.model_router.providers.openai import OpenAIProvider

    providers: dict[str, LLMProvider] = {}
    providers["anthropic"] = AnthropicProvider(
        model_name=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
    )
    providers["openai"] = OpenAIProvider(
        model_name=os.environ.get("OPENAI_MODEL", "gpt-4o"),
    )
    # Always include BedrockProvider in non-paper mode (charter §7.5: Bedrock-first).
    # If credentials are unavailable, health_check() will report is_healthy=False.
    providers["bedrock"] = BedrockProvider(
        model_id=os.environ.get(
            "BEDROCK_MODEL_ID", BEDROCK_MODEL_IDS["claude-sonnet"]
        ),
    )

    return providers
