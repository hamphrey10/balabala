"""Security guards encoding DEMO-only and secret hygiene principles."""

from __future__ import annotations

import re
from typing import Any

from quant_deriv_ai.core.exceptions import TradingModeError
from quant_deriv_ai.core.models import TradingMode

_SECRET_KEYS = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|login|credential)",
    re.IGNORECASE,
)


def assert_demo_only(mode: TradingMode | str) -> TradingMode:
    """Fail closed unless trading mode is DEMO."""
    value = TradingMode(mode) if not isinstance(mode, TradingMode) else mode
    if value is not TradingMode.DEMO:
        msg = "live/real trading is forbidden — DEMO only"
        raise TradingModeError(msg)
    return value


def redact_secrets(data: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy with sensitive-looking values redacted."""
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if _SECRET_KEYS.search(str(key)):
            redacted[key] = "***REDACTED***"
        elif isinstance(value, dict):
            redacted[key] = redact_secrets(value)
        else:
            redacted[key] = value
    return redacted
