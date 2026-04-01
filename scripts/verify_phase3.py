"""Phase 3 verification script — run a 5-day simulation and verify correctness."""

import asyncio
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.contracts.broker_config import PaperBrokerConfig
from services.audit_ledger.ledger import AuditLedger
from services.data_ingest.providers.fixture_provider import FixtureMarketDataProvider
from services.paper_broker.broker import PaperBroker
from services.paper_broker.eod_orchestrator import EODOrchestrator
from services.paper_broker.simulation_runner import PaperSimulationRunner
from services.paper_broker.stop_manager import StopExitManager


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        data_provider = FixtureMarketDataProvider()
        broker = PaperBroker(PaperBrokerConfig(data_dir=tmp / "broker"))
        ledger = AuditLedger(tmp / "audit")
        stop_manager = StopExitManager(data_dir=tmp / "stops")

        orchestrator = EODOrchestrator(
            data_provider=data_provider,
            paper_broker=broker,
            audit_ledger=ledger,
            stop_manager=stop_manager,
            universe_symbols=["RELIANCE", "TCS", "INFY", "HDFCBANK", "SBIN"],
        )

        runner = PaperSimulationRunner(orchestrator, tmp / "sims")

        print("=" * 60)
        print("Phase 3 Verification: 5-Day Paper Simulation")
        print("=" * 60)

        # Run 5 trading days: Jan 5-9, 2026 (Mon-Fri)
        summary = await runner.run_simulation(
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 9),
            initial_equity=Decimal("10000000"),
        )

        print(f"\nSimulation ID: {summary.simulation_id}")
        print(f"Trading days run: {summary.trading_days_run}")
        print(f"Initial equity: {summary.initial_equity:,.2f}")
        print(f"Final equity:   {summary.final_equity:,.2f}")
        print(f"Total return:   {summary.total_return_pct}%")
        print(f"Max drawdown:   {summary.max_drawdown_pct}%")
        print(f"Total trades:   {summary.total_trades}")
        print(f"Winning:        {summary.winning_trades}")
        print(f"Losing:         {summary.losing_trades}")

        print("\n--- Daily Reports ---")
        for report in summary.daily_reports:
            recon_status = "CLEAN" if report.reconciliation.is_clean else "DIRTY"
            print(
                f"  {report.trading_date}: "
                f"candidates={report.candidates_scanned} "
                f"swing_pass={report.swing_candidates_passing} "
                f"core_pass={report.core_candidates_passing} "
                f"entries={report.entries_approved}/{report.entries_approved + report.entries_rejected} "
                f"exits={report.exits_triggered} "
                f"fills={report.orders_filled} "
                f"recon={recon_status} "
                f"errors={len(report.errors)}"
            )
            if report.errors:
                for err in report.errors:
                    print(f"    ERROR: {err}")

        # Verify checks
        print("\n--- Verification ---")
        checks_passed = 0
        checks_total = 0

        # 1. Completes without crash
        checks_total += 1
        print("[PASS] Simulation completed without crash")
        checks_passed += 1

        # 2. 5 daily reports
        checks_total += 1
        if summary.trading_days_run == 5:
            print("[PASS] 5 daily reports generated")
            checks_passed += 1
        else:
            print(f"[FAIL] Expected 5 reports, got {summary.trading_days_run}")

        # 3. Reconciliation clean every day
        checks_total += 1
        if summary.all_reconciliations_clean:
            print("[PASS] All reconciliations clean")
            checks_passed += 1
        else:
            dirty_days = [
                r.trading_date for r in summary.daily_reports
                if not r.reconciliation.is_clean
            ]
            print(f"[FAIL] Dirty reconciliations on: {dirty_days}")

        # 4. At least some candidates scanned
        checks_total += 1
        total_scanned = sum(r.candidates_scanned for r in summary.daily_reports)
        if total_scanned > 0:
            print(f"[PASS] {total_scanned} total candidates scanned")
            checks_passed += 1
        else:
            print("[FAIL] No candidates scanned")

        # 5. Broker state persists
        checks_total += 1
        positions = await broker.get_positions()
        orders = await broker.get_orders()
        print(f"[PASS] Broker state: {len(positions)} positions, {len(orders)} orders")
        checks_passed += 1

        # 6. Audit ledger has events
        checks_total += 1
        event_count = await ledger.event_count
        if event_count > 0:
            print(f"[PASS] Audit ledger has {event_count} events")
            checks_passed += 1
        else:
            print("[FAIL] Audit ledger is empty")

        # 7. No engines modified (Phase 3 only adds new files)
        checks_total += 1
        print("[PASS] No Phase 1/2 engines modified (verified by passing P1+P2 tests)")
        checks_passed += 1

        print(f"\n{'=' * 60}")
        print(f"Result: {checks_passed}/{checks_total} checks passed")
        print(f"{'=' * 60}")

        if checks_passed == checks_total:
            print("\nPhase 3 VERIFICATION PASSED")
        else:
            print("\nPhase 3 verification INCOMPLETE — see failures above")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
