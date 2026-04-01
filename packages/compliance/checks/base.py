"""Base protocol for compliance checks."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from packages.contracts.compliance import ComplianceContext, ComplianceResult


@runtime_checkable
class ComplianceCheck(Protocol):
    """Protocol that all compliance checks must implement."""

    name: str
    description: str
    blocking: bool  # If True, failure prevents live arming

    async def run(self, context: ComplianceContext) -> ComplianceResult: ...
