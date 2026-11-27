"""Core primitives: event bus, models, exceptions, logging."""

from __future__ import annotations

from quant_deriv_ai.core.event_bus import Event, EventBus, EventHandler
from quant_deriv_ai.core.exceptions import (
    ConfigError,
    LiveAccountForbiddenError,
    Mt5ConnectionError,
    Mt5Error,
    Mt5NotAvailableError,
    QuantDerivError,
    RiskViolationError,
    TradingModeError,
)
from quant_deriv_ai.core.logging import configure_logging, get_logger
from quant_deriv_ai.core.models import (
    AccountMode,
    InstrumentRef,
    OrderSide,
    SignalIntent,
    TradingMode,
)

__all__ = [
    "AccountMode",
    "ConfigError",
    "Event",
    "EventBus",
    "EventHandler",
    "InstrumentRef",
    "LiveAccountForbiddenError",
    "Mt5ConnectionError",
    "Mt5Error",
    "Mt5NotAvailableError",
    "OrderSide",
    "QuantDerivError",
    "RiskViolationError",
    "SignalIntent",
    "TradingMode",
    "TradingModeError",
    "configure_logging",
    "get_logger",
]
