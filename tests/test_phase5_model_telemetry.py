"""Phase 5 tests — ModelTelemetry."""

from __future__ import annotations

from packages.contracts.llm import ModelRole, ModelTelemetrySummary
from packages.model_router.telemetry import ModelTelemetry


class TestModelTelemetry:
    def test_initial_summary_empty(self) -> None:
        t = ModelTelemetry()
        summary = t.get_summary()
        assert isinstance(summary, ModelTelemetrySummary)
        assert summary.total_calls == 0
        assert summary.overall_success_rate == 0.0

    def test_success_increments_counts(self) -> None:
        t = ModelTelemetry()
        t.record_success(ModelRole.BLOCKER_SCAN, "fixture", 50)
        t.record_success(ModelRole.BLOCKER_SCAN, "fixture", 60)
        summary = t.get_summary()
        assert summary.total_calls == 2
        assert summary.overall_success_rate == 1.0
        stats = summary.stats[0]
        assert stats.success_count == 2
        assert stats.failure_count == 0

    def test_failure_increments_counts(self) -> None:
        t = ModelTelemetry()
        t.record_success(ModelRole.BLOCKER_SCAN, "fixture", 50)
        t.record_failure(ModelRole.BLOCKER_SCAN, "fixture", 100)
        summary = t.get_summary()
        assert summary.total_calls == 2
        assert summary.overall_success_rate == 0.5
        stats = summary.stats[0]
        assert stats.success_count == 1
        assert stats.failure_count == 1

    def test_fallback_rate(self) -> None:
        t = ModelTelemetry()
        t.record_success(
            ModelRole.BLOCKER_SCAN, "fixture", 50, fallback_used=False
        )
        t.record_success(
            ModelRole.BLOCKER_SCAN, "fixture", 60, fallback_used=True
        )
        summary = t.get_summary()
        stats = summary.stats[0]
        assert stats.fallback_rate == 0.5

    def test_parse_failure_rate(self) -> None:
        t = ModelTelemetry()
        t.record_success(ModelRole.TRADE_CARD, "anthropic", 100)
        t.record_success(ModelRole.TRADE_CARD, "anthropic", 120)
        t.record_parse_failure(ModelRole.TRADE_CARD, "anthropic")
        summary = t.get_summary()
        stats = [
            s
            for s in summary.stats
            if s.role == ModelRole.TRADE_CARD
            and s.provider == "anthropic"
        ]
        assert len(stats) == 1
        assert stats[0].parse_failure_rate == 0.5

    def test_multiple_roles_tracked_separately(self) -> None:
        t = ModelTelemetry()
        t.record_success(ModelRole.BLOCKER_SCAN, "fixture", 50)
        t.record_success(ModelRole.TRADE_CARD, "fixture", 80)
        t.record_success(ModelRole.EXPLANATION, "fixture", 30)
        summary = t.get_summary()
        assert summary.total_calls == 3
        assert len(summary.stats) == 3

    def test_summary_validates_as_contract(self) -> None:
        t = ModelTelemetry()
        t.record_success(ModelRole.BLOCKER_SCAN, "fixture", 50)
        t.record_failure(ModelRole.BLOCKER_SCAN, "anthropic", 200)
        summary = t.get_summary()
        # Should be a valid Pydantic model
        assert isinstance(summary, ModelTelemetrySummary)
        dumped = summary.model_dump()
        assert "stats" in dumped
        assert "total_calls" in dumped
