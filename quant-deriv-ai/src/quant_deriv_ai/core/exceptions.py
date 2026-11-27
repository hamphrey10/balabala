"""Centralized exception hierarchy for QUANT DERIV AI."""

from __future__ import annotations


class QuantDerivError(Exception):
    """Base exception for all QUANT DERIV AI errors."""


class ConfigError(QuantDerivError):
    """Raised when configuration is missing, invalid, or unsafe."""


class TradingModeError(QuantDerivError):
    """Raised when a non-DEMO / live trading mode is requested."""


class RiskViolationError(QuantDerivError):
    """Raised when an action would violate the risk policy."""


class DependencyError(QuantDerivError):
    """Raised when a required runtime dependency is unavailable."""


class AgentError(QuantDerivError):
    """Raised for agent lifecycle or interface violations."""


class PersistenceError(QuantDerivError):
    """Raised for storage/read/write failures."""


class Mt5Error(QuantDerivError):
    """Base error for MetaTrader 5 connector failures."""

    def __init__(self, message: str, *, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class Mt5NotAvailableError(Mt5Error):
    """Raised when the MetaTrader5 package or terminal is unavailable."""


class Mt5ConnectionError(Mt5Error):
    """Raised when initialize/login/reconnect fails."""


class LiveAccountForbiddenError(TradingModeError):
    """Raised when a LIVE/real (or non-DEMO) account is detected — all ops blocked."""
