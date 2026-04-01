"""ConfigSnapshot schema — frozen snapshot of runtime configuration."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from .enums import Mode, RegimeClass


class RiskLimits(BaseModel):
    """Risk limit parameters as defined in charter §6.3."""

    model_config = ConfigDict(strict=True, frozen=True)

    swing_risk_per_trade_pct: Decimal = Decimal("0.50")
    """Max risk per swing trade as % of equity. Charter default: 0.50%."""

    core_add_risk_pct: Decimal = Decimal("0.25")
    """Max risk per core add as % of equity. Charter default: 0.25%."""

    core_position_cap_pct: Decimal = Decimal("12.0")
    """Hard cap on core position size as % of equity. Charter default: 12%."""

    swing_position_cap_pct: Decimal = Decimal("8.0")
    """Hard cap on swing position size as % of equity. Charter default: 8%."""

    sector_cap_pct: Decimal = Decimal("25.0")
    """Preferred sector concentration cap. Charter default: 25%."""

    aggregate_open_risk_pct: Decimal = Decimal("4.0")
    """Preferred aggregate open risk cap. Charter default: 4%."""

    max_new_swing_entries_per_day: int = 2
    """Max new swing entries per trading day. Charter default: 2."""


class ConfigSnapshot(BaseModel):
    """
    Frozen snapshot of all runtime configuration at a point in time.

    Used for audit trail and drift detection. Captures the full configuration
    state so any run can be fully reproduced or audited. The config_checksum
    enables detection of unauthorized configuration changes (charter §10).
    """

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "snapshot_id": "550e8400-e29b-41d4-a716-446655440020",
                    "captured_at": "2026-03-26T09:00:00Z",
                    "mode": "paper",
                    "armed_live": False,
                    "risk_limits": {
                        "swing_risk_per_trade_pct": "0.50",
                        "core_add_risk_pct": "0.25",
                        "core_position_cap_pct": "12.0",
                        "swing_position_cap_pct": "8.0",
                        "sector_cap_pct": "25.0",
                        "aggregate_open_risk_pct": "4.0",
                        "max_new_swing_entries_per_day": 2,
                    },
                    "regime_state": "green",
                    "universe_size": 98,
                    "active_blockers_count": 3,
                    "config_checksum": "a3b4c5d6e7f8a1b2c3d4e5f6a7b8c9d0",
                },
            ]
        },
    )

    snapshot_id: str
    """UUID for this snapshot."""

    captured_at: datetime
    """UTC timestamp when the snapshot was taken."""

    mode: Mode
    armed_live: bool
    risk_limits: RiskLimits
    regime_state: RegimeClass

    universe_size: int
    """Number of symbols in the active universe."""

    active_blockers_count: int
    """Number of active blockers across the universe at snapshot time."""

    config_checksum: str
    """SHA-256 of the serialized configuration for drift detection."""
