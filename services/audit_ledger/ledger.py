"""Audit ledger — append-only audit log for all significant system actions.

Charter: "operator should always know what was considered, blocked,
scheduled, executed, changed, or failed."

Storage: JSON Lines (.jsonl) files, one per day. Append-only.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from pathlib import Path

from packages.contracts.audit_event import AuditEvent

logger = logging.getLogger(__name__)


class AuditLedger:
    """
    Append-only audit log. Every significant system action is recorded.
    Never raises exceptions that crash the calling service.
    """

    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def _file_for_date(self, target_date: date) -> Path:
        return self._storage_dir / f"audit_{target_date.isoformat()}.jsonl"

    async def record(self, event: AuditEvent, trading_date: date | None = None) -> None:
        """Record a single audit event.

        When *trading_date* is provided the event timestamp is replaced with
        midnight UTC on that date so backtest events are filed under the
        simulated trading date rather than today's wall-clock date.
        """
        try:
            if trading_date is not None:
                sim_ts = datetime(
                    trading_date.year,
                    trading_date.month,
                    trading_date.day,
                    0, 0, 0,
                    tzinfo=UTC,
                )
                event = event.model_copy(update={"timestamp": sim_ts})
            event_date = event.timestamp.date()
            path = self._file_for_date(event_date)
            line = event.model_dump_json() + "\n"
            with open(path, "a") as f:
                f.write(line)
        except Exception:
            logger.exception("Failed to record audit event %s", event.event_id)

    async def record_batch(
        self, events: list[AuditEvent], trading_date: date | None = None
    ) -> None:
        """Record a batch of audit events."""
        for event in events:
            await self.record(event, trading_date=trading_date)

    async def query(
        self,
        event_types: list[str] | None = None,
        symbol: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query the ledger with optional filters."""
        results: list[AuditEvent] = []

        # Determine which files to scan
        jsonl_files = sorted(self._storage_dir.glob("audit_*.jsonl"))

        for path in jsonl_files:
            # Extract date from filename for coarse filtering
            try:
                file_date_str = path.stem.replace("audit_", "")
                file_date = date.fromisoformat(file_date_str)
            except ValueError:
                continue

            if start_time and file_date < start_time.date():
                continue
            if end_time and file_date > end_time.date():
                continue

            try:
                with open(path) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            event = AuditEvent.model_validate_json(line)
                        except Exception:
                            logger.warning("Skipping malformed audit line in %s", path)
                            continue

                        # Apply filters
                        if event_types and event.event_type not in event_types:
                            continue
                        if symbol and event.related_symbol != symbol:
                            continue
                        if start_time and event.timestamp < start_time:
                            continue
                        if end_time and event.timestamp > end_time:
                            continue

                        results.append(event)
                        if len(results) >= limit:
                            return results
            except Exception:
                logger.exception("Failed to read audit file %s", path)

        return results

    async def get_events_for_date(self, target_date: date) -> list[AuditEvent]:
        """Get all events for a specific date."""
        path = self._file_for_date(target_date)
        if not path.exists():
            return []

        events: list[AuditEvent] = []
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(AuditEvent.model_validate_json(line))
                    except Exception:
                        logger.warning("Skipping malformed audit line")
        except Exception:
            logger.exception("Failed to read audit file for %s", target_date)

        return events

    async def get_events_for_intent(self, intent_id: str) -> list[AuditEvent]:
        """Get all events related to a specific intent ID."""
        results: list[AuditEvent] = []

        for path in sorted(self._storage_dir.glob("audit_*.jsonl")):
            try:
                with open(path) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        # Quick check before full parse
                        if intent_id not in line:
                            continue
                        try:
                            event = AuditEvent.model_validate_json(line)
                            if event.related_intent_id == intent_id:
                                results.append(event)
                        except Exception:
                            continue
            except Exception:
                logger.exception("Failed to read audit file %s", path)

        return results

    @property
    async def event_count(self) -> int:
        """Count total events across all files."""
        count = 0
        for path in self._storage_dir.glob("audit_*.jsonl"):
            try:
                with open(path) as f:
                    count += sum(1 for line in f if line.strip())
            except Exception:
                logger.exception("Failed to count events in %s", path)
        return count
