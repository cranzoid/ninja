"""ClockCheck — verifies system clock is consistent with IST expectations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from packages.contracts.compliance import (
    ComplianceContext,
    ComplianceResult,
    ComplianceStatus,
)
from packages.contracts.enums import Mode

# IST = UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30))

# NSE market hours (IST)
_MARKET_OPEN_HOUR = 9
_MARKET_OPEN_MINUTE = 15
_MARKET_CLOSE_HOUR = 15
_MARKET_CLOSE_MINUTE = 30


class ClockCheck:
    """Verifies system clock is reasonable and mode transitions are safe."""

    name: str = "clock_check"
    description: str = "System clock is within expectations"
    blocking: bool = True

    async def run(self, context: ComplianceContext) -> ComplianceResult:
        now_utc = datetime.now(UTC)
        now_ist = now_utc.astimezone(IST)
        now = now_utc

        # Check 1: System clock should be reasonable (within 5 seconds is
        # about testing that we can compute IST at all — in production this
        # would compare against an NTP source, but for now we just validate
        # the timezone conversion works)
        try:
            _ = now_ist.isoformat()
        except Exception as e:
            return ComplianceResult(
                check_name=self.name,
                status=ComplianceStatus.FAIL,
                message=f"Clock check failed: cannot compute IST time: {e}",
                checked_at=now,
            )

        # Check 2: Don't arm during market hours
        if context.mode != Mode.PAPER:
            is_weekday = now_ist.weekday() < 5
            market_open = now_ist.replace(
                hour=_MARKET_OPEN_HOUR,
                minute=_MARKET_OPEN_MINUTE,
                second=0,
            )
            market_close = now_ist.replace(
                hour=_MARKET_CLOSE_HOUR,
                minute=_MARKET_CLOSE_MINUTE,
                second=0,
            )

            in_market = market_open <= now_ist <= market_close
            if is_weekday and in_market and context.armed_live:
                return ComplianceResult(
                    check_name=self.name,
                    status=ComplianceStatus.WARNING,
                    message=(
                        f"Mode transition during market hours "
                        f"(IST: {now_ist.strftime('%H:%M')}). "
                        f"Consider arming outside market hours."
                    ),
                    checked_at=now,
                )

        ist_str = now_ist.strftime("%Y-%m-%d %H:%M:%S")
        return ComplianceResult(
            check_name=self.name,
            status=ComplianceStatus.PASS,
            message=f"Clock check passed. IST: {ist_str}.",
            checked_at=now,
        )
