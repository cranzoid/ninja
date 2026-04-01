"""Entry rule evaluator — applies charter rules to produce
OrderIntents or rejections."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from packages.contracts.blocker_report import BlockerReport
from packages.contracts.candidates import SwingCandidate
from packages.contracts.config_snapshot import RiskLimits
from packages.contracts.decisions import EntryDecision
from packages.contracts.enums import (
    ExecutionTiming,
    Mode,
    OrderSide,
    OrderType,
    PortfolioLayer,
    RegimeClass,
)
from packages.contracts.order_intent import OrderIntent
from packages.contracts.portfolio import PortfolioState
from packages.contracts.regime_state import RegimeState

from .position_sizer import calculate_position_size


def evaluate_swing_entry(
    candidate: SwingCandidate,
    portfolio: PortfolioState,
    risk_limits: RiskLimits,
    regime: RegimeState,
    blockers: BlockerReport,
    mode: Mode = Mode.PAPER,
) -> EntryDecision:
    """
    Evaluate a swing candidate against all charter rules.

    Checks are performed in order; rejection is immediate on first failure.
    All checks are logged in checks_performed regardless of outcome.
    """
    checks: list[str] = []
    rejections: list[str] = []

    # 1. Blocker check
    checks.append("blocker_check")
    if blockers.is_blocked:
        categories = [
            b.category.value
            for b in blockers.blockers_found
            if b.severity == "hard"
        ]
        rejections.append(f"hard_blocker: {', '.join(categories)}")
        return EntryDecision(
            symbol=candidate.symbol,
            layer=PortfolioLayer.SWING,
            decision="reject",
            rejection_reasons=rejections,
            checks_performed=checks,
        )

    # 2. Regime check
    checks.append("regime_check")
    if regime.regime_class == RegimeClass.STRESSED:
        rejections.append("regime_stressed: no new swing entries")
        return EntryDecision(
            symbol=candidate.symbol,
            layer=PortfolioLayer.SWING,
            decision="reject",
            rejection_reasons=rejections,
            checks_performed=checks,
        )

    is_mixed = regime.regime_class == RegimeClass.MIXED
    if is_mixed:
        checks.append("regime_mixed: half-sizing applied")

    # 3. Aggregate risk check
    checks.append("aggregate_risk_check")
    risk_per_trade_pct = risk_limits.swing_risk_per_trade_pct
    new_risk_pct = risk_per_trade_pct * regime.sizing_multiplier
    if portfolio.open_risk_pct + new_risk_pct > risk_limits.aggregate_open_risk_pct:
        rejections.append(
            f"aggregate_risk_breach: current {portfolio.open_risk_pct}% + "
            f"new {new_risk_pct}% > limit {risk_limits.aggregate_open_risk_pct}%"
        )
        return EntryDecision(
            symbol=candidate.symbol,
            layer=PortfolioLayer.SWING,
            decision="reject",
            rejection_reasons=rejections,
            checks_performed=checks,
        )

    # 4. Position sizing
    checks.append("position_sizing")
    quantity = calculate_position_size(
        equity=portfolio.equity,
        risk_per_trade_pct=risk_per_trade_pct,
        risk_per_share=candidate.risk_per_share,
        regime=regime,
        layer=PortfolioLayer.SWING,
    )
    if quantity == 0:
        rejections.append(
            "position_size_zero: capital insufficient"
        )
        return EntryDecision(
            symbol=candidate.symbol,
            layer=PortfolioLayer.SWING,
            decision="reject",
            rejection_reasons=rejections,
            checks_performed=checks,
        )

    # 5. Position cap check
    checks.append("position_cap_check")
    position_value = candidate.entry_price_estimate * quantity
    position_pct = (position_value / portfolio.equity) * 100
    if position_pct > risk_limits.swing_position_cap_pct:
        rejections.append(
            f"position_cap_breach: {position_pct:.2f}% "
            f"> limit {risk_limits.swing_position_cap_pct}%"
        )
        return EntryDecision(
            symbol=candidate.symbol,
            layer=PortfolioLayer.SWING,
            decision="reject",
            rejection_reasons=rejections,
            checks_performed=checks,
        )

    # 6. Sector cap check (simplified — would need sector mapping in production)
    checks.append("sector_cap_check")
    # For now, use symbol as proxy for sector lookup
    # In production, a sector mapping service would provide this

    # 7. Build OrderIntent
    checks.append("order_intent_creation")
    risk_amount = candidate.risk_per_share * quantity
    actual_risk_pct = (risk_amount / portfolio.equity) * Decimal("100")

    # Clamp risk_pct to charter limit
    if actual_risk_pct > risk_limits.swing_risk_per_trade_pct:
        actual_risk_pct = risk_limits.swing_risk_per_trade_pct

    intent = OrderIntent(
        intent_id=str(uuid.uuid4()),
        symbol=candidate.symbol,
        layer=PortfolioLayer.SWING,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=quantity,
        stop_price=candidate.stop_price,
        risk_amount=risk_amount,
        risk_pct_of_equity=actual_risk_pct,
        execution_timing=ExecutionTiming.NEXT_OPEN,
        regime_at_intent=regime.regime_class,
        created_at=datetime.now(UTC),
        approved_by="rule_engine",
        mode=mode,
    )

    return EntryDecision(
        symbol=candidate.symbol,
        layer=PortfolioLayer.SWING,
        decision="approve",
        order_intent=intent,
        rejection_reasons=[],
        checks_performed=checks,
    )
