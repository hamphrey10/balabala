"""Pydantic models for Deriv WebSocket connector state (read-only)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DerivConnectionState(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    BLOCKED_LIVE = "blocked_live"


class DerivAccountSnapshot(BaseModel):
    """Subset of official ``authorize`` / ``balance`` response fields."""

    model_config = ConfigDict(extra="forbid")

    loginid: str
    currency: str
    balance: float
    is_virtual: int = Field(description="1 = demo/virtual, 0 = real")
    email: str = ""
    fullname: str = ""
    country: str = ""
    scopes: list[str] = Field(default_factory=list)

    @property
    def is_demo(self) -> bool:
        return self.is_virtual == 1


class DerivConnectionStatus(BaseModel):
    """Public status payload — never includes tokens."""

    model_config = ConfigDict(extra="forbid")

    state: DerivConnectionState
    endpoint: str | None = None
    app_id: str | None = None
    loginid: str | None = None
    is_virtual: int | None = None
    currency: str | None = None
    balance: float | None = None
    last_error: str | None = None
    live_lock_engaged: bool = False
