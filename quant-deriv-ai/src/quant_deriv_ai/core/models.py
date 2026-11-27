"""Typed domain models shared across packages (Pydantic)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TradingMode(StrEnum):
    """Allowed trading modes. Live is defined only to reject it explicitly."""

    DEMO = "demo"
    LIVE = "live"


class AccountMode(StrEnum):
    """Broker account classification."""

    DEMO = "demo"
    REAL = "real"
    UNKNOWN = "unknown"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class InstrumentRef(BaseModel):
    """Reference to a market instrument discovered at runtime (never hard-assumed)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(..., min_length=1)
    broker: str = Field(default="deriv_mt5")
    asset_class: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol")
    @classmethod
    def _strip_symbol(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "symbol must not be empty"
            raise ValueError(msg)
        return stripped


class SignalIntent(BaseModel):
    """Candidate trade intent emitted by a strategy/agent — must pass risk before execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intent_id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    side: OrderSide
    volume: float = Field(..., gt=0)
    rationale: str = ""
    edge_demonstrated: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class SystemStatus(BaseModel):
    """High-level runtime status snapshot for CLI / monitoring."""

    model_config = ConfigDict(extra="forbid")

    version: str
    trading_mode: TradingMode
    environment: str
    packages_ready: bool
    mt5_importable: bool
    mt5_notes: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
