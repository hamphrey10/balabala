"""Deriv WebSocket API connector — DEMO-only, read-only (primary broker connection)."""

from __future__ import annotations

from quant_deriv_ai.execution.deriv.client import DerivClient, ensure_no_order_apis
from quant_deriv_ai.execution.deriv.credentials import DerivCredentials, load_credentials_from_env
from quant_deriv_ai.execution.deriv.live_lock import DerivLiveLock
from quant_deriv_ai.execution.deriv.models import (
    DerivAccountSnapshot,
    DerivConnectionState,
    DerivConnectionStatus,
)

__all__ = [
    "DerivAccountSnapshot",
    "DerivClient",
    "DerivConnectionState",
    "DerivConnectionStatus",
    "DerivCredentials",
    "DerivLiveLock",
    "ensure_no_order_apis",
    "load_credentials_from_env",
]
