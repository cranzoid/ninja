import os
from enum import StrEnum


class Mode(StrEnum):
    PAPER = "paper"
    SHADOW_LIVE = "shadow-live"
    LIVE = "live"


class Config:
    """Platform configuration from environment variables."""

    def __init__(self) -> None:
        self.database_url: str = os.environ.get(
            "DATABASE_URL", "postgresql://localhost:5432/trading_platform_dev"
        )
        self.aws_region: str = os.environ.get("AWS_REGION", "ap-south-1")
        self.mode: Mode = self._parse_mode(os.environ.get("MODE", "paper"))
        self.armed_live: bool = os.environ.get("ARMED_LIVE", "false").lower() == "true"
        self.log_level: str = os.environ.get("LOG_LEVEL", "INFO")

    def _parse_mode(self, value: str) -> Mode:
        try:
            return Mode(value)
        except ValueError:
            allowed = ", ".join(m.value for m in Mode)
            msg = f"Invalid MODE '{value}'. Must be one of: {allowed}"
            raise ValueError(msg) from None


config = Config()
