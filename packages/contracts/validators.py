"""Validation utilities for contract schemas.

Primary entry point for validating LLM outputs against contract schemas
before they enter the system (charter §7.3).
"""

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def validate_contract(
    data: dict[str, Any], model_class: type[T]
) -> tuple[T | None, list[str]]:
    """
    Validate a Python dict against a contract schema.

    Returns (parsed model, []) on success.
    Returns (None, [error messages]) on failure. Never raises.

    Note: Requires properly-typed Python objects for strict-mode models
    (e.g., Decimal instances for Decimal fields, datetime for datetime fields).
    Use validate_json_string for validating raw LLM JSON outputs.
    """
    try:
        return model_class.model_validate(data), []
    except ValidationError as exc:
        return None, [
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]


def validate_json_string(
    json_str: str, model_class: type[T]
) -> tuple[T | None, list[str]]:
    """
    Validate a raw JSON string against a contract schema.

    Primary entry point for validating LLM outputs. Uses Pydantic's
    JSON parser which handles type coercion from JSON primitives (string
    to Decimal, ISO string to datetime, etc.).

    Returns (parsed model, []) on success.
    Returns (None, [error messages]) on failure. Never raises.
    """
    try:
        return model_class.model_validate_json(json_str), []
    except ValidationError as exc:
        return None, [
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
    except (json.JSONDecodeError, ValueError) as exc:
        return None, [str(exc)]
