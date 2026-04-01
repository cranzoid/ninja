"""Tests for GET /api/compliance/status.

Updated for Phase 7: response is now ComplianceStatusResponse with
`report` (ComplianceReport) and `live_ready` fields.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestCompliance:
    @pytest.mark.asyncio
    async def test_compliance_returns_valid_status(self, client: AsyncClient) -> None:
        """GET /api/compliance/status returns valid ComplianceStatusResponse."""
        response = await client.get("/api/compliance/status")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "report" in data
        assert "live_ready" in data
        report = data["report"]
        assert "mode" in report
        assert "results" in report
        assert "all_blocking_passed" in report
        assert "generated_at" in report

    @pytest.mark.asyncio
    async def test_paper_mode_checks_present(self, client: AsyncClient) -> None:
        """Paper mode checks are included with correct check names."""
        response = await client.get("/api/compliance/status")
        assert response.status_code == 200
        results = response.json()["data"]["report"]["results"]
        check_names = {c["check_name"] for c in results}

        # Phase 6 checks
        expected_checks = {
            "env_vars",
            "kill_switch",
            "mode_flag",
            "broker_auth",
            "broker_health",
            "audit_sink",
            "config_checksum",
            "clock_check",
        }
        assert expected_checks.issubset(check_names)

    @pytest.mark.asyncio
    async def test_paper_mode_skips_broker_checks(
        self, client: AsyncClient
    ) -> None:
        """Broker auth and health checks are skipped in paper mode."""
        response = await client.get("/api/compliance/status")
        assert response.status_code == 200
        results = response.json()["data"]["report"]["results"]
        broker_checks = [
            c for c in results if c["check_name"] in (
                "broker_auth",
                "broker_health",
                "kill_switch",
            )
        ]
        for check in broker_checks:
            assert check["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_audit_sink_passes(self, client: AsyncClient) -> None:
        """audit_sink check passes (ledger writable and readable)."""
        response = await client.get("/api/compliance/status")
        assert response.status_code == 200
        results = response.json()["data"]["report"]["results"]
        audit_check = next(
            c for c in results if c["check_name"] == "audit_sink"
        )
        assert audit_check["status"] == "pass"

    @pytest.mark.asyncio
    async def test_mode_is_paper(self, client: AsyncClient) -> None:
        """Compliance status reports paper mode."""
        response = await client.get("/api/compliance/status")
        assert response.json()["data"]["report"]["mode"] == "paper"
