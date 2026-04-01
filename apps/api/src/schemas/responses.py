"""Standard API response envelopes for the operator console API."""

from datetime import UTC, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standard single-item response envelope."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool
    data: T | None = None
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated list response envelope."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool
    data: list[T]
    total: int
    page: int
    page_size: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
