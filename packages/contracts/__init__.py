"""Contracts package — all Pydantic schema contracts for the trading platform."""

from .audit_event import AuditEvent
from .blocker_report import BlockerDetail, BlockerReport
from .broker import (
    BrokerAdapter,
    BrokerAuthError,
    BrokerConfig,
    BrokerHealth,
    BrokerNetworkError,
    BrokerSession,
    LiveRunReport,
    OrderModification,
    ShadowRunReport,
)
from .broker_config import PaperBrokerConfig, Quote
from .candidates import CoreCandidate, SwingCandidate
from .compliance import (
    ComplianceContext,
    ComplianceReport,
    ComplianceResult,
    ComplianceStatus,
)
from .config_snapshot import ConfigSnapshot, RiskLimits
from .corp_action import CorporateAction, CorporateActionType
from .decisions import EntryDecision, ExitDecision
from .enums import (
    BlockerCategory,
    ExecutionTiming,
    Mode,
    OrderSide,
    OrderStatus,
    OrderType,
    OverrideAction,
    PortfolioLayer,
    RegimeClass,
    SignalDirection,
)
from .eod_report import EODRunReport
from .exceptions import InvalidStateTransition
from .llm import (
    ExplanationOutput,
    LLMResponse,
    ModelRole,
    ModelRouterConfig,
    ModelTelemetrySummary,
    ProviderConfig,
    ProviderHealth,
    ProviderRoleStats,
    RoleRouting,
    RoutingDecision,
)
from .order_intent import OrderIntent
from .order_state import OrderRecord, OrderStateTransition
from .portfolio import PortfolioState, Position
from .reconciliation import ReconciliationReport
from .regime_state import RegimeState
from .risk import PortfolioRisk
from .simulation import SimulationSummary
from .trade_card import TradeCard
from .validators import validate_contract, validate_json_string

__all__ = [
    "AuditEvent",
    "BlockerCategory",
    "BlockerDetail",
    "BlockerReport",
    "BrokerAdapter",
    "BrokerAuthError",
    "BrokerConfig",
    "BrokerHealth",
    "BrokerNetworkError",
    "BrokerSession",
    "ComplianceContext",
    "ComplianceReport",
    "ComplianceResult",
    "ComplianceStatus",
    "ConfigSnapshot",
    "CoreCandidate",
    "CorporateAction",
    "CorporateActionType",
    "EODRunReport",
    "EntryDecision",
    "ExecutionTiming",
    "ExitDecision",
    "ExplanationOutput",
    "InvalidStateTransition",
    "LLMResponse",
    "LiveRunReport",
    "Mode",
    "ModelRole",
    "ModelRouterConfig",
    "ModelTelemetrySummary",
    "OrderIntent",
    "OrderModification",
    "OrderRecord",
    "OrderSide",
    "OrderStateTransition",
    "OrderStatus",
    "OrderType",
    "OverrideAction",
    "PaperBrokerConfig",
    "PortfolioLayer",
    "PortfolioRisk",
    "PortfolioState",
    "Position",
    "ProviderConfig",
    "ProviderHealth",
    "ProviderRoleStats",
    "Quote",
    "ReconciliationReport",
    "RegimeClass",
    "RegimeState",
    "RiskLimits",
    "RoleRouting",
    "RoutingDecision",
    "ShadowRunReport",
    "SignalDirection",
    "SimulationSummary",
    "SwingCandidate",
    "TradeCard",
    "validate_contract",
    "validate_json_string",
]
