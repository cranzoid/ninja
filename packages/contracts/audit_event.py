"""AuditEvent schema — foundation of the audit ledger."""

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from .enums import Mode


class AuditEvent(BaseModel):
    """
    Every significant action in the platform produces an AuditEvent.

    Foundation of the audit-ledger service. Every trade must be
    explainable and audit-ready (charter §4). Schema failures, retries,
    and model fallbacks are all first-class audit events (charter §7.3).

    Common event_type values:
        trade_card_generated, blocker_scan_complete, order_intent_created,
        order_submitted, order_filled, stop_triggered, override_applied,
        regime_change, compliance_check, schema_validation_failure,
        model_fallback.
    """

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "event_id": "550e8400-e29b-41d4-a716-446655440010",
                    "timestamp": "2026-03-26T09:15:00Z",
                    "event_type": "trade_card_generated",
                    "source_service": "model-router",
                    "mode": "paper",
                    "payload": {
                        "symbol": "RELIANCE",
                        "model_provider": "anthropic",
                        "model_id": "claude-sonnet-4-6",
                    },
                    "related_symbol": "RELIANCE",
                    "related_intent_id": None,
                    "operator_visible": True,
                },
                {
                    "event_id": "550e8400-e29b-41d4-a716-446655440011",
                    "timestamp": "2026-03-26T09:30:00Z",
                    "event_type": "schema_validation_failure",
                    "source_service": "model-router",
                    "mode": "paper",
                    "payload": {
                        "model_id": "claude-haiku-4-5",
                        "errors": ["stop_price must be below entry_price_target"],
                        "retry_count": 1,
                    },
                    "related_symbol": "INFY",
                    "related_intent_id": None,
                    "operator_visible": True,
                },
            ]
        },
    )

    event_id: str
    """UUID for this event."""

    timestamp: datetime
    """UTC timestamp."""

    event_type: str
    """Classification of this event."""

    source_service: str
    """Which service produced this event."""

    mode: Mode

    payload: dict[str, Any]
    """
    Event-specific data. The one dict[str, Any] exception in the contract
    layer because audit payloads vary by event type. Must be JSON-serializable.
    """

    related_symbol: str | None = None
    """NSE symbol this event relates to, if applicable."""

    related_intent_id: str | None = None
    """OrderIntent ID this event relates to, if applicable."""

    operator_visible: bool = True
    """Whether to surface this event in the console alerts feed."""

    @field_validator("payload")
    @classmethod
    def validate_payload_serializable(cls, v: dict[str, Any]) -> dict[str, Any]:
        try:
            json.dumps(v)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"payload must be JSON-serializable: {exc}") from exc
        return v
