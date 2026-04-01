"""Common enumerations used across all contract schemas."""

from enum import StrEnum


class PortfolioLayer(StrEnum):
    """Which portfolio sleeve the trade belongs to."""

    CORE = "core"
    SWING = "swing"


class SignalDirection(StrEnum):
    """Trade direction. No short selling in V1."""

    LONG = "long"
    FLAT = "flat"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(StrEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ExecutionTiming(StrEnum):
    """All execution is next-day open per charter §6.5."""

    NEXT_OPEN = "next_open"


class BlockerCategory(StrEnum):
    """Blocker categories from charter §6.6 rules S1-S5 and R1-R5."""

    EARNINGS_WINDOW = "earnings_window"
    CORPORATE_ACTION = "corporate_action"
    CREDIBILITY_RISK = "credibility_risk"
    OVERNIGHT_GAP = "overnight_gap"
    SECTOR_SHOCK = "sector_shock"
    AGGREGATE_RISK = "aggregate_risk"
    TIME_STOP = "time_stop"
    REGIME_BLOCK = "regime_block"


class RegimeClass(StrEnum):
    """Market regime classification from charter §6.7."""

    GREEN = "green"
    MIXED = "mixed"
    STRESSED = "stressed"


class Mode(StrEnum):
    """Platform operating mode."""

    PAPER = "paper"
    SHADOW_LIVE = "shadow-live"
    LIVE = "live"


class OverrideAction(StrEnum):
    """Operator-allowed override actions — risk-reducing only per charter §12."""

    CANCEL_ENTRY = "cancel_entry"
    REDUCE_SIZE = "reduce_size"
    TIGHTEN_STOP = "tighten_stop"
    CLOSE_POSITION = "close_position"
    FREEZE_SYMBOL = "freeze_symbol"
