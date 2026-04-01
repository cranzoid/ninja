"""Position sizer — calculates share quantities respecting risk and regime rules."""

from __future__ import annotations

import math
from decimal import Decimal

from packages.contracts.enums import PortfolioLayer
from packages.contracts.regime_state import RegimeState


def calculate_position_size(
    equity: Decimal,
    risk_per_trade_pct: Decimal,
    risk_per_share: Decimal,
    regime: RegimeState,
    layer: PortfolioLayer,
) -> int:
    """
    Calculate position size in shares.

    Base: (equity * risk_per_trade_pct / 100) / risk_per_share, floored to int.
    Then apply regime sizing_multiplier.

    Returns 0 if the position is too large for capital (caller should reject).
    """
    if risk_per_share <= 0:
        return 0

    risk_budget = equity * risk_per_trade_pct / Decimal("100")
    base_shares = risk_budget / risk_per_share

    # Apply regime multiplier
    adjusted = base_shares * regime.sizing_multiplier

    # Floor to integer
    quantity = math.floor(float(adjusted))

    return quantity
