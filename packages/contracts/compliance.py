"""Compliance gate contracts — context, results, and report schemas.

Phase 6: Pre-live compliance gate per charter section 9.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from .broker import BrokerConfig
from .enums import Mode


class ComplianceStatus(StrEnum):
    """Status of a single compliance check."""

    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"
    WARNING = "warning"


class ComplianceContext(BaseModel):
    """Input context for running compliance checks."""

    model_config = ConfigDict(strict=True, frozen=True)

    mode: Mode
    broker_config: BrokerConfig
    env_vars_present: list[str]
    static_ip: str | None = None
    armed_live: bool
    config_checksum: str | None = None


class ComplianceResult(BaseModel):
    """Result of a single compliance check."""

    model_config = ConfigDict(strict=True, frozen=True)

    check_name: str
    status: ComplianceStatus
    message: str
    checked_at: datetime
    """IST datetime of the check."""


class ComplianceReport(BaseModel):
    """Aggregate compliance gate report."""

    model_config = ConfigDict(strict=True, frozen=True)

    results: list[ComplianceResult]
    all_blocking_passed: bool
    generated_at: datetime
    """IST datetime of report generation."""

    mode: Mode
