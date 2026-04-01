"""Order state schemas — lifecycle tracking for orders."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from .enums import OrderStatus
from .order_intent import OrderIntent


class OrderStateTransition(BaseModel):
    """A single state transition in an order's lifecycle."""

    model_config = ConfigDict(strict=True, frozen=True)

    order_id: str
    from_status: OrderStatus
    to_status: OrderStatus
    timestamp: datetime
    reason: str | None = None
    fill_price: Decimal | None = None
    filled_qty: int | None = None


class OrderRecord(BaseModel):
    """Full lifecycle record of an order."""

    model_config = ConfigDict(strict=True, frozen=False)

    order_id: str
    intent: OrderIntent
    current_status: OrderStatus
    submitted_at: datetime | None = None
    filled_at: datetime | None = None
    fill_price: Decimal | None = None
    filled_qty: int = 0
    remaining_qty: int
    transitions: list[OrderStateTransition] = []
    created_at: datetime
