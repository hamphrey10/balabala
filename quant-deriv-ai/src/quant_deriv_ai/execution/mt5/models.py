"""Pydantic contracts for MT5 connector data (read-only; no order types)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Mt5ConnectionState(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    BLOCKED_LIVE = "blocked_live"
    ERROR = "error"


class AccountSnapshot(BaseModel):
    """Subset of ``account_info()`` fields used by QUANT DERIV AI."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    login: int
    trade_mode: int
    trade_mode_label: str
    balance: float
    equity: float
    margin: float
    margin_free: float
    margin_level: float
    profit: float
    currency: str
    server: str
    company: str
    name: str = ""
    leverage: int = 0
    trade_allowed: bool = False


class TerminalSnapshot(BaseModel):
    """Subset of ``terminal_info()`` fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connected: bool
    name: str
    company: str
    path: str
    data_path: str = ""
    build: int = 0
    trade_allowed: bool = False
    ping_last: int = 0


class SymbolCharacteristics(BaseModel):
    """Selected fields from ``symbol_info()`` — discovered dynamically, never assumed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str = ""
    path: str = ""
    digits: int = 0
    point: float = 0.0
    spread: int = 0
    volume_min: float = 0.0
    volume_max: float = 0.0
    volume_step: float = 0.0
    trade_contract_size: float = 0.0
    trade_tick_size: float = 0.0
    trade_tick_value: float = 0.0
    currency_base: str = ""
    currency_profit: str = ""
    currency_margin: str = ""
    bid: float = 0.0
    ask: float = 0.0
    trade_mode: int = 0
    visible: bool = False
    select: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)


class TickData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    time: datetime
    bid: float
    ask: float
    last: float = 0.0
    volume: float = 0.0
    flags: int = 0


class Candle(BaseModel):
    """OHLCV bar from ``copy_rates_*``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    timeframe: str
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int = 0
    spread: int = 0
    real_volume: int = 0


class PositionInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ticket: int
    symbol: str
    type: int
    volume: float
    price_open: float
    price_current: float
    sl: float = 0.0
    tp: float = 0.0
    profit: float = 0.0
    swap: float = 0.0
    time: datetime | None = None
    magic: int = 0
    comment: str = ""
    identifier: int = 0


class DealInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ticket: int
    order: int = 0
    position_id: int = 0
    symbol: str = ""
    type: int = 0
    entry: int = 0
    volume: float = 0.0
    price: float = 0.0
    profit: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    time: datetime | None = None
    magic: int = 0
    comment: str = ""


class ConnectionStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Mt5ConnectionState
    server: str | None = None
    login: int | None = None
    trade_mode_label: str | None = None
    terminal_connected: bool | None = None
    terminal_path: str | None = None
    last_error: str | None = None
    heartbeat_ok: bool | None = None
    live_lock_engaged: bool = False
