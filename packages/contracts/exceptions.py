"""Custom exceptions for the trading platform."""


class InvalidStateTransition(Exception):
    """Raised when an order state transition is not valid."""

    def __init__(
        self,
        from_status: str,
        to_status: str,
        reason: str = "",
    ) -> None:
        self.from_status = from_status
        self.to_status = to_status
        msg = f"Invalid transition: {from_status} -> {to_status}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)
