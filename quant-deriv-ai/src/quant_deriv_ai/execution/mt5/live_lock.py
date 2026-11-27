"""Strict live-account lock — forbids ANY connector operation on REAL/contest accounts.

Once engaged, the lock cannot be cleared without an explicit process restart
(new ``LiveAccountLock`` instance). This encodes SECURITY.md / RISK_POLICY.md
DEMO-only for the MT5 connector layer.
"""

from __future__ import annotations

import threading

from quant_deriv_ai.core.exceptions import LiveAccountForbiddenError
from quant_deriv_ai.execution.mt5.constants import (
    ACCOUNT_TRADE_MODE_DEMO,
    account_trade_mode_label,
)


class LiveAccountLock:
    """Process-scoped gate: DEMO allowed; any other trade_mode blocks forever."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._engaged = False
        self._reason: str | None = None
        self._trade_mode: int | None = None

    @property
    def engaged(self) -> bool:
        with self._lock:
            return self._engaged

    @property
    def reason(self) -> str | None:
        with self._lock:
            return self._reason

    def assert_allowed(self) -> None:
        """Raise if the live lock is engaged."""
        with self._lock:
            if self._engaged:
                msg = (
                    self._reason
                    or "LIVE/real account lock engaged — all MT5 operations forbidden"
                )
                raise LiveAccountForbiddenError(msg)

    def evaluate_trade_mode(self, trade_mode: int, *, login: int | None = None) -> None:
        """Accept DEMO; engage permanent lock for contest/real/unknown non-demo."""
        with self._lock:
            if trade_mode == ACCOUNT_TRADE_MODE_DEMO:
                return
            label = account_trade_mode_label(trade_mode)
            login_part = f" login={login}" if login is not None else ""
            reason = (
                f"non-DEMO account detected (trade_mode={trade_mode}/{label}){login_part} — "
                "LIVE/contest accounts are forbidden; all MT5 operations blocked"
            )
            self._engaged = True
            self._reason = reason
            self._trade_mode = trade_mode
            raise LiveAccountForbiddenError(reason)
