"""Strict live-account lock for Deriv — forbids ops when is_virtual != 1."""

from __future__ import annotations

import threading

from quant_deriv_ai.core.exceptions import LiveAccountForbiddenError
from quant_deriv_ai.execution.deriv.constants import IS_VIRTUAL_DEMO


class DerivLiveLock:
    """Process-scoped gate: virtual/demo allowed; real accounts block forever."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._engaged = False
        self._reason: str | None = None

    @property
    def engaged(self) -> bool:
        with self._lock:
            return self._engaged

    @property
    def reason(self) -> str | None:
        with self._lock:
            return self._reason

    def assert_allowed(self) -> None:
        with self._lock:
            if self._engaged:
                msg = (
                    self._reason
                    or "LIVE/real Deriv account lock engaged — all operations forbidden"
                )
                raise LiveAccountForbiddenError(msg)

    def evaluate_is_virtual(self, is_virtual: int, *, loginid: str | None = None) -> None:
        """Accept demo (is_virtual=1); engage permanent lock for real accounts."""
        with self._lock:
            if is_virtual == IS_VIRTUAL_DEMO:
                return
            login_part = f" loginid={loginid}" if loginid else ""
            reason = (
                f"non-DEMO Deriv account detected (is_virtual={is_virtual}){login_part} — "
                "real accounts are forbidden; all Deriv operations blocked"
            )
            self._engaged = True
            self._reason = reason
            raise LiveAccountForbiddenError(reason)
