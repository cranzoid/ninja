"""Model telemetry — tracks per-role, per-provider call statistics."""

from __future__ import annotations

import statistics
import threading

from packages.contracts.llm import (
    ModelRole,
    ModelTelemetrySummary,
    ProviderRoleStats,
)


class _RoleProviderMetrics:
    """Mutable metrics accumulator for a single role+provider pair."""

    def __init__(self) -> None:
        self.total_calls = 0
        self.success_count = 0
        self.failure_count = 0
        self.fallback_count = 0
        self.parse_failure_count = 0
        self.latencies: list[int] = []


class ModelTelemetry:
    """Tracks per-role, per-provider call statistics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics: dict[tuple[str, str], _RoleProviderMetrics] = {}

    def _key(self, role: ModelRole, provider: str) -> tuple[str, str]:
        return (role.value, provider)

    def _get_or_create(
        self, role: ModelRole, provider: str
    ) -> _RoleProviderMetrics:
        key = self._key(role, provider)
        if key not in self._metrics:
            self._metrics[key] = _RoleProviderMetrics()
        return self._metrics[key]

    def record_success(
        self,
        role: ModelRole,
        provider: str,
        latency_ms: int,
        fallback_used: bool = False,
    ) -> None:
        with self._lock:
            m = self._get_or_create(role, provider)
            m.total_calls += 1
            m.success_count += 1
            m.latencies.append(latency_ms)
            if fallback_used:
                m.fallback_count += 1

    def record_failure(
        self,
        role: ModelRole,
        provider: str,
        latency_ms: int,
    ) -> None:
        with self._lock:
            m = self._get_or_create(role, provider)
            m.total_calls += 1
            m.failure_count += 1
            m.latencies.append(latency_ms)

    def record_parse_failure(self, role: ModelRole, provider: str) -> None:
        with self._lock:
            m = self._get_or_create(role, provider)
            m.parse_failure_count += 1

    def get_summary(self) -> ModelTelemetrySummary:
        with self._lock:
            stats: list[ProviderRoleStats] = []
            total_calls = 0
            total_successes = 0
            total_fallbacks = 0

            for (role_val, provider), m in self._metrics.items():
                total_calls += m.total_calls
                total_successes += m.success_count
                total_fallbacks += m.fallback_count

                avg_lat = (
                    statistics.mean(m.latencies) if m.latencies else 0.0
                )
                p95_lat = (
                    _percentile(m.latencies, 95) if m.latencies else 0.0
                )
                fallback_rate = (
                    m.fallback_count / m.total_calls
                    if m.total_calls > 0
                    else 0.0
                )
                parse_fail_rate = (
                    m.parse_failure_count / m.total_calls
                    if m.total_calls > 0
                    else 0.0
                )

                stats.append(
                    ProviderRoleStats(
                        provider=provider,
                        role=ModelRole(role_val),
                        total_calls=m.total_calls,
                        success_count=m.success_count,
                        failure_count=m.failure_count,
                        avg_latency_ms=round(avg_lat, 1),
                        p95_latency_ms=round(p95_lat, 1),
                        fallback_rate=round(fallback_rate, 4),
                        parse_failure_rate=round(parse_fail_rate, 4),
                    )
                )

            overall_success_rate = (
                total_successes / total_calls if total_calls > 0 else 0.0
            )
            overall_fallback_rate = (
                total_fallbacks / total_calls if total_calls > 0 else 0.0
            )

            return ModelTelemetrySummary(
                stats=stats,
                total_calls=total_calls,
                overall_success_rate=round(overall_success_rate, 4),
                overall_fallback_rate=round(overall_fallback_rate, 4),
            )


def _percentile(data: list[int], pct: int) -> float:
    """Calculate a percentile from a list of values."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * pct / 100
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return float(sorted_data[-1])
    return float(sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f]))
