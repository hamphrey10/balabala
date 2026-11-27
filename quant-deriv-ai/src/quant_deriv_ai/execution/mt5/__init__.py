"""MetaTrader5 connector — DEMO-only, no order placement in LOT-002."""

from __future__ import annotations

from quant_deriv_ai.execution.mt5.client import Mt5Client, detect_terminal, import_mt5
from quant_deriv_ai.execution.mt5.credentials import Mt5Credentials, load_credentials_from_env
from quant_deriv_ai.execution.mt5.live_lock import LiveAccountLock
from quant_deriv_ai.execution.mt5.models import (
    AccountSnapshot,
    Candle,
    ConnectionStatus,
    DealInfo,
    Mt5ConnectionState,
    PositionInfo,
    SymbolCharacteristics,
    TerminalSnapshot,
    TickData,
)

__all__ = [
    "AccountSnapshot",
    "Candle",
    "ConnectionStatus",
    "DealInfo",
    "LiveAccountLock",
    "Mt5Client",
    "Mt5ConnectionState",
    "Mt5Credentials",
    "PositionInfo",
    "SymbolCharacteristics",
    "TerminalSnapshot",
    "TickData",
    "detect_terminal",
    "import_mt5",
    "load_credentials_from_env",
]
