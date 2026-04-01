"""Live-V1 risk limits and validation — calibrated for ~₹50,000 capital.

Phase 7: Tiny Live. These limits are tighter than paper defaults to protect
real capital during initial live deployment.
"""

from __future__ import annotations

from decimal import Decimal

from packages.contracts.config_snapshot import RiskLimits

# --- Live-V1 Risk Limits ---
# Calibrated for ₹50,000 initial capital per charter §6.3 / Gate C.
LIVE_V1_RISK_LIMITS = RiskLimits(
    swing_risk_per_trade_pct=Decimal("0.50"),
    core_add_risk_pct=Decimal("0.25"),
    core_position_cap_pct=Decimal("10.0"),
    swing_position_cap_pct=Decimal("8.0"),
    sector_cap_pct=Decimal("25.0"),
    aggregate_open_risk_pct=Decimal("4.0"),
    max_new_swing_entries_per_day=2,
)

# Live-V1 supplementary limits (not in RiskLimits model but enforced by
# LiveEODOrchestrator and LiveConfigValidator)
LIVE_V1_MAX_POSITIONS_SWING = 3
LIVE_V1_MAX_POSITIONS_CORE = 4
LIVE_V1_MIN_POSITION_VALUE_INR = Decimal("3000")
LIVE_V1_MAX_POSITION_VALUE_INR = Decimal("5000")
LIVE_V1_DAILY_LOSS_LIMIT_PCT = Decimal("0.02")
LIVE_V1_MAX_CAPITAL_INR = Decimal("50000")
LIVE_V1_MAX_POSITION_SIZE_PCT = Decimal("0.10")
LIVE_V1_MAX_PORTFOLIO_RISK_PCT = Decimal("0.06")
LIVE_V1_MAX_SECTOR_CONCENTRATION_PCT = Decimal("0.25")


def validate_live_limits(
    limits: RiskLimits,
    capital_inr: float,
) -> list[str]:
    """Return warnings if limits seem inconsistent with declared capital.

    Warnings do not block — they are logged and shown in the compliance report.
    """
    warnings: list[str] = []
    capital = Decimal(str(capital_inr))

    # max_position_value should be <= capital * max_position_size_pct
    max_pos_value = capital * LIVE_V1_MAX_POSITION_SIZE_PCT
    if max_pos_value < LIVE_V1_MAX_POSITION_VALUE_INR:
        warnings.append(
            f"max_position_value_inr ({LIVE_V1_MAX_POSITION_VALUE_INR}) > "
            f"capital * max_position_size_pct ({max_pos_value})"
        )

    # max_capital >= declared capital
    if capital > LIVE_V1_MAX_CAPITAL_INR:
        warnings.append(
            f"max_capital_inr ({LIVE_V1_MAX_CAPITAL_INR}) < "
            f"declared capital ({capital})"
        )

    # min_position_value >= 2000 (friction floor)
    if Decimal("2000") > LIVE_V1_MIN_POSITION_VALUE_INR:
        warnings.append(
            f"min_position_value_inr ({LIVE_V1_MIN_POSITION_VALUE_INR}) < "
            f"₹2,000 friction floor"
        )

    # max positions sanity cap
    total_positions = LIVE_V1_MAX_POSITIONS_SWING + LIVE_V1_MAX_POSITIONS_CORE
    if total_positions > 10:
        warnings.append(
            f"Total max positions ({total_positions}) > 10 sanity cap"
        )

    return warnings
