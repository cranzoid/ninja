"""Phase 6 tests — ShadowLiveRunner (8+ tests)."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest
import pytest_asyncio

from packages.brokers.mock_broker import MockBrokerAdapter
from packages.brokers.shadow_runner import ShadowLiveRunner
from packages.contracts.broker import BrokerConfig, ShadowRunReport
from services.audit_ledger.ledger import AuditLedger
from services.data_ingest.providers.fixture_provider import FixtureMarketDataProvider


@pytest.fixture
def broker_config() -> BrokerConfig:
    return BrokerConfig(
        broker_name="mock",
        base_url="http://localhost",
        dry_run=True,
    )


@pytest_asyncio.fixture
async def audit_ledger(tmp_path: Path) -> AuditLedger:
    return AuditLedger(tmp_path / "audit")


@pytest_asyncio.fixture
async def mock_broker(
    broker_config: BrokerConfig, audit_ledger: AuditLedger
) -> MockBrokerAdapter:
    return MockBrokerAdapter(
        config=broker_config, audit_ledger=audit_ledger
    )


@pytest_asyncio.fixture
async def shadow_runner(
    mock_broker: MockBrokerAdapter, audit_ledger: AuditLedger
) -> ShadowLiveRunner:
    data_provider = FixtureMarketDataProvider()
    return ShadowLiveRunner(
        data_provider=data_provider,
        mock_broker=mock_broker,
        audit_ledger=audit_ledger,
    )


class TestShadowLiveRunner:
    @pytest.mark.asyncio
    async def test_run_shadow_eod_completes(
        self, shadow_runner: ShadowLiveRunner
    ) -> None:
        os.environ["MODE"] = "paper"
        os.environ.pop("ARMED_LIVE", None)
        try:
            report = await shadow_runner.run_shadow_eod(date(2026, 1, 6))
            assert isinstance(report, ShadowRunReport)
            assert report.trading_date == date(2026, 1, 6)
        finally:
            os.environ.pop("MODE", None)

    @pytest.mark.asyncio
    async def test_report_contract_validates(
        self, shadow_runner: ShadowLiveRunner
    ) -> None:
        os.environ["MODE"] = "paper"
        os.environ.pop("ARMED_LIVE", None)
        try:
            report = await shadow_runner.run_shadow_eod(date(2026, 1, 6))
            # Validate it can be serialized/deserialized
            json_str = report.model_dump_json()
            restored = ShadowRunReport.model_validate_json(json_str)
            assert restored.trading_date == report.trading_date
        finally:
            os.environ.pop("MODE", None)

    @pytest.mark.asyncio
    async def test_intents_passed_to_dry_run_adapter(
        self, shadow_runner: ShadowLiveRunner, audit_ledger: AuditLedger
    ) -> None:
        os.environ["MODE"] = "paper"
        os.environ.pop("ARMED_LIVE", None)
        try:
            report = await shadow_runner.run_shadow_eod(date(2026, 1, 6))
            # All intents should have corresponding dry-run orders
            assert len(report.orders_dry_run) == len(report.intents_generated)
        finally:
            os.environ.pop("MODE", None)

    @pytest.mark.asyncio
    async def test_no_real_orders_submitted(
        self, shadow_runner: ShadowLiveRunner, mock_broker: MockBrokerAdapter
    ) -> None:
        os.environ["MODE"] = "paper"
        os.environ.pop("ARMED_LIVE", None)
        try:
            await shadow_runner.run_shadow_eod(date(2026, 1, 6))
            # Mock broker get_positions should still be empty
            positions = await mock_broker.get_positions()
            assert len(positions) == 0
        finally:
            os.environ.pop("MODE", None)

    @pytest.mark.asyncio
    async def test_errors_captured_not_raised(
        self, audit_ledger: AuditLedger
    ) -> None:
        """If a step fails, error is captured in errors list, not raised."""
        from unittest.mock import AsyncMock

        config = BrokerConfig(
            broker_name="mock", base_url="http://localhost", dry_run=True
        )
        broker = MockBrokerAdapter(config=config, audit_ledger=audit_ledger)

        # Create a data provider that will fail
        bad_provider = AsyncMock()
        bad_provider.fetch_ohlcv = AsyncMock(
            side_effect=RuntimeError("data fetch failed")
        )

        runner = ShadowLiveRunner(
            data_provider=bad_provider,
            mock_broker=broker,
            audit_ledger=audit_ledger,
        )

        os.environ["MODE"] = "paper"
        os.environ.pop("ARMED_LIVE", None)
        try:
            report = await runner.run_shadow_eod(date(2026, 1, 6))
            assert len(report.errors) > 0
            assert any("data" in e.lower() for e in report.errors)
        finally:
            os.environ.pop("MODE", None)

    @pytest.mark.asyncio
    async def test_regime_state_in_report(
        self, shadow_runner: ShadowLiveRunner
    ) -> None:
        os.environ["MODE"] = "paper"
        os.environ.pop("ARMED_LIVE", None)
        try:
            report = await shadow_runner.run_shadow_eod(date(2026, 1, 6))
            assert report.regime_state in ("green", "mixed", "stressed")
        finally:
            os.environ.pop("MODE", None)

    @pytest.mark.asyncio
    async def test_candidates_scanned_nonnegative(
        self, shadow_runner: ShadowLiveRunner
    ) -> None:
        os.environ["MODE"] = "paper"
        os.environ.pop("ARMED_LIVE", None)
        try:
            report = await shadow_runner.run_shadow_eod(date(2026, 1, 6))
            assert report.candidates_scanned >= 0
        finally:
            os.environ.pop("MODE", None)

    @pytest.mark.asyncio
    async def test_blocked_in_armed_live_mode(
        self, shadow_runner: ShadowLiveRunner
    ) -> None:
        os.environ["MODE"] = "live"
        os.environ["ARMED_LIVE"] = "true"
        try:
            with pytest.raises(OSError):
                await shadow_runner.run_shadow_eod(date(2026, 1, 6))
        finally:
            os.environ.pop("MODE", None)
            os.environ.pop("ARMED_LIVE", None)
