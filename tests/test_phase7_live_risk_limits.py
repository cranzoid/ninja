"""Phase 7 tests — live risk limits, validation, and config checksum check.

Tests LIVE_V1_RISK_LIMITS, validate_live_limits(), and the updated
ConfigChecksumCheck with blocking=True in live mode.
"""

from __future__ import annotations

import os
from decimal import Decimal
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from packages.compliance.checks.config_checksum import ConfigChecksumCheck
from packages.contracts.broker import BrokerConfig
from packages.contracts.compliance import (
    ComplianceContext,
    ComplianceStatus,
)
from packages.contracts.config_snapshot import RiskLimits
from packages.contracts.enums import Mode
from packages.utils.live_config import (
    LIVE_V1_MAX_CAPITAL_INR,
    LIVE_V1_MAX_POSITION_VALUE_INR,
    LIVE_V1_RISK_LIMITS,
    validate_live_limits,
)


class TestLiveV1RiskLimits:
    def test_limits_validate_as_risk_limits_contract(self) -> None:
        """LIVE_V1_RISK_LIMITS validates correctly as RiskLimits contract."""
        assert isinstance(LIVE_V1_RISK_LIMITS, RiskLimits)
        assert LIVE_V1_RISK_LIMITS.swing_risk_per_trade_pct == Decimal("0.50")
        assert LIVE_V1_RISK_LIMITS.core_add_risk_pct == Decimal("0.25")
        assert LIVE_V1_RISK_LIMITS.max_new_swing_entries_per_day == 2

    def test_limits_are_frozen(self) -> None:
        """LIVE_V1_RISK_LIMITS is immutable (frozen model)."""
        with pytest.raises(ValidationError):
            LIVE_V1_RISK_LIMITS.swing_risk_per_trade_pct = Decimal("1.0")

    def test_max_capital_is_50k(self) -> None:
        """Hard cap is 50,000 INR."""
        assert Decimal("50000") == LIVE_V1_MAX_CAPITAL_INR

    def test_max_position_value_is_5k(self) -> None:
        """Max position value is 5,000 INR at 50k capital."""
        assert Decimal("5000") == LIVE_V1_MAX_POSITION_VALUE_INR


class TestValidateLiveLimits:
    def test_no_warnings_with_consistent_limits(self) -> None:
        """No warnings when limits are consistent with 50k capital."""
        warnings = validate_live_limits(LIVE_V1_RISK_LIMITS, 50000)
        assert len(warnings) == 0

    def test_warns_on_capital_exceeds_max(self) -> None:
        """Warns if declared capital exceeds max_capital_inr."""
        warnings = validate_live_limits(LIVE_V1_RISK_LIMITS, 100000)
        assert any("max_capital_inr" in w for w in warnings)

    def test_no_warning_on_min_position_value(self) -> None:
        """No warning when min_position_value >= 2000."""
        # Default is 3000, so should be no warning
        warnings = validate_live_limits(LIVE_V1_RISK_LIMITS, 50000)
        assert not any("friction floor" in w for w in warnings)


class TestConfigChecksumCheck:
    @pytest.mark.asyncio
    async def test_blocking_is_true(self) -> None:
        """ConfigChecksumCheck.blocking is True in Phase 7."""
        check = ConfigChecksumCheck()
        assert check.blocking is True

    @pytest.mark.asyncio
    async def test_live_mode_fail_if_checksum_missing(self) -> None:
        """In live mode, missing CONFIG_CHECKSUM env var -> FAIL."""
        check = ConfigChecksumCheck()
        context = ComplianceContext(
            mode=Mode.LIVE,
            broker_config=BrokerConfig(
                broker_name="zerodha", base_url="https://api.kite.trade", dry_run=False
            ),
            env_vars_present=[],
            armed_live=True,
            config_checksum="abc123",
        )

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CONFIG_CHECKSUM", None)
            result = await check.run(context)

        assert result.status == ComplianceStatus.FAIL
        assert "required in live mode" in result.message

    @pytest.mark.asyncio
    async def test_live_mode_fail_if_checksum_mismatch(self) -> None:
        """In live mode, checksum mismatch -> FAIL."""
        check = ConfigChecksumCheck()
        context = ComplianceContext(
            mode=Mode.LIVE,
            broker_config=BrokerConfig(
                broker_name="zerodha", base_url="https://api.kite.trade", dry_run=False
            ),
            env_vars_present=[],
            armed_live=True,
            config_checksum="current_checksum_abc",
        )

        with patch.dict(os.environ, {"CONFIG_CHECKSUM": "expected_checksum_xyz"}):
            result = await check.run(context)

        assert result.status == ComplianceStatus.FAIL
        assert "mismatch" in result.message

    @pytest.mark.asyncio
    async def test_live_mode_pass_if_checksum_matches(self) -> None:
        """In live mode, matching checksum -> PASS."""
        check = ConfigChecksumCheck()
        checksum = "matching_checksum_123456"
        context = ComplianceContext(
            mode=Mode.LIVE,
            broker_config=BrokerConfig(
                broker_name="zerodha", base_url="https://api.kite.trade", dry_run=False
            ),
            env_vars_present=[],
            armed_live=True,
            config_checksum=checksum,
        )

        with patch.dict(os.environ, {"CONFIG_CHECKSUM": checksum}):
            result = await check.run(context)

        assert result.status == ComplianceStatus.PASS

    @pytest.mark.asyncio
    async def test_shadow_live_mode_warning_not_fail(self) -> None:
        """In shadow-live mode, missing checksum -> WARNING (not FAIL)."""
        check = ConfigChecksumCheck()
        context = ComplianceContext(
            mode=Mode.SHADOW_LIVE,
            broker_config=BrokerConfig(
                broker_name="mock", base_url="http://localhost", dry_run=True
            ),
            env_vars_present=[],
            armed_live=False,
            config_checksum="some_checksum",
        )

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CONFIG_CHECKSUM", None)
            result = await check.run(context)

        assert result.status == ComplianceStatus.WARNING

    @pytest.mark.asyncio
    async def test_paper_mode_skipped(self) -> None:
        """In paper mode, config checksum check is SKIPPED."""
        check = ConfigChecksumCheck()
        context = ComplianceContext(
            mode=Mode.PAPER,
            broker_config=BrokerConfig(
                broker_name="mock", base_url="http://localhost", dry_run=True
            ),
            env_vars_present=[],
            armed_live=False,
        )

        result = await check.run(context)
        assert result.status == ComplianceStatus.SKIPPED
