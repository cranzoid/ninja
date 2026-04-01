"""Risk center router — portfolio risk metrics and limit utilization."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from packages.contracts.config_snapshot import RiskLimits
from packages.contracts.enums import PortfolioLayer
from packages.contracts.risk import PortfolioRisk
from services.risk_engine.calculator import calculate_portfolio_risk

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse, PaginatedResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/risk", tags=["risk"])


class SectorUtilization(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    sector: str
    exposure_pct: Decimal
    limit_pct: Decimal
    utilization_pct: Decimal


class LimitUtilization(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    aggregate_risk_used_pct: Decimal
    aggregate_risk_limit_pct: Decimal
    aggregate_risk_utilization_pct: Decimal
    sector_utilization: dict[str, SectorUtilization]
    worst_sector: str | None


class PositionRiskDetail(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    symbol: str
    layer: PortfolioLayer
    risk_amount: Decimal
    risk_pct: Decimal
    position_pct: Decimal
    sector: str


class RiskCenterData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    portfolio_risk: PortfolioRisk
    risk_limits: RiskLimits
    limit_utilization: LimitUtilization
    position_risk_breakdown: list[PositionRiskDetail]


@router.get("/current", response_model=APIResponse[RiskCenterData])
async def get_current_risk(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[RiskCenterData]:
    """Return current portfolio risk metrics and limit utilization."""
    positions = await state.paper_broker.get_positions()
    equity = await state.get_portfolio_equity()
    limits = state.config.risk_limits

    portfolio_risk = calculate_portfolio_risk(positions, equity, limits)

    # Sector utilization
    sector_util: dict[str, SectorUtilization] = {}
    worst_sector: str | None = None
    worst_pct = Decimal("0")

    for sector, exp_pct in portfolio_risk.sector_exposure.items():
        util_pct = (
            (exp_pct / limits.sector_cap_pct * 100).quantize(Decimal("0.01"))
            if limits.sector_cap_pct > 0
            else Decimal("0")
        )
        sector_util[sector] = SectorUtilization(
            sector=sector,
            exposure_pct=exp_pct,
            limit_pct=limits.sector_cap_pct,
            utilization_pct=util_pct,
        )
        if exp_pct > worst_pct:
            worst_pct = exp_pct
            worst_sector = sector

    agg_util = (
        (portfolio_risk.open_risk_pct / limits.aggregate_open_risk_pct * 100).quantize(
            Decimal("0.01")
        )
        if limits.aggregate_open_risk_pct > 0
        else Decimal("0")
    )

    limit_util = LimitUtilization(
        aggregate_risk_used_pct=portfolio_risk.open_risk_pct,
        aggregate_risk_limit_pct=limits.aggregate_open_risk_pct,
        aggregate_risk_utilization_pct=agg_util,
        sector_utilization=sector_util,
        worst_sector=worst_sector,
    )

    # Per-position breakdown
    breakdown: list[PositionRiskDetail] = []
    for pos in positions:
        risk_pct = (
            (pos.risk_amount / equity * 100).quantize(Decimal("0.01"))
            if equity > 0
            else Decimal("0")
        )
        pos_value = pos.current_price * pos.quantity
        pos_pct = (
            (pos_value / equity * 100).quantize(Decimal("0.01"))
            if equity > 0
            else Decimal("0")
        )
        breakdown.append(
            PositionRiskDetail(
                symbol=pos.symbol,
                layer=pos.layer,
                risk_amount=pos.risk_amount,
                risk_pct=risk_pct,
                position_pct=pos_pct,
                sector=pos.sector,
            )
        )

    data = RiskCenterData(
        portfolio_risk=portfolio_risk,
        risk_limits=limits,
        limit_utilization=limit_util,
        position_risk_breakdown=breakdown,
    )
    return APIResponse[RiskCenterData](success=True, data=data)


@router.get("/history", response_model=PaginatedResponse[PortfolioRisk])
async def get_risk_history(
    state: Annotated[AppState, Depends(get_app_state)],
    days: int = 30,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[PortfolioRisk]:
    """Return portfolio risk snapshots from EOD run history."""
    risks = [r.portfolio_risk for r in state.eod_run_history]
    # Most recent first
    risks = list(reversed(risks[-days:]))
    total = len(risks)
    start = (page - 1) * page_size
    return PaginatedResponse[PortfolioRisk](
        success=True,
        data=risks[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )
