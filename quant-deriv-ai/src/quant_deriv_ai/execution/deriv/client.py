"""Deriv WebSocket connector — DEMO-only, read-only (no orders).

Uses documented Deriv JSON APIs over WebSocket:
``authorize``, ``balance``, ``ping``.

Intentionally absent: ``buy``, ``sell``, ``proposal`` purchase flows,
``cashier``, and any order placement.
"""

from __future__ import annotations

import contextlib
import threading

from quant_deriv_ai.core.exceptions import DerivConnectionError, LiveAccountForbiddenError
from quant_deriv_ai.core.logging import get_logger
from quant_deriv_ai.execution.deriv.credentials import DerivCredentials
from quant_deriv_ai.execution.deriv.live_lock import DerivLiveLock
from quant_deriv_ai.execution.deriv.models import (
    DerivAccountSnapshot,
    DerivConnectionState,
    DerivConnectionStatus,
)
from quant_deriv_ai.execution.deriv.transport import DerivTransport, WebsocketTransport

log = get_logger(__name__)


class DerivClient:
    """Thread-safe Deriv API client with DEMO fail-closed lock."""

    def __init__(
        self,
        credentials: DerivCredentials | None = None,
        *,
        transport: DerivTransport | None = None,
        timeout_s: float = 30.0,
        live_lock: DerivLiveLock | None = None,
    ) -> None:
        self._credentials = credentials
        self._transport: DerivTransport = transport or WebsocketTransport(timeout_s=timeout_s)
        self._owns_default_transport = transport is None
        self._timeout_s = timeout_s
        self._live_lock = live_lock or DerivLiveLock()
        self._api_lock = threading.RLock()
        self._state = DerivConnectionState.DISCONNECTED
        self._account: DerivAccountSnapshot | None = None
        self._last_error: str | None = None
        self._endpoint: str | None = None
        self._app_id: str | None = None

    @property
    def state(self) -> DerivConnectionState:
        return self._state

    @property
    def live_lock(self) -> DerivLiveLock:
        return self._live_lock

    def connect(self, credentials: DerivCredentials | None = None) -> DerivAccountSnapshot:
        """Open WebSocket, authorize, verify DEMO (is_virtual=1), reject real."""
        self._live_lock.assert_allowed()
        creds = credentials or self._credentials
        if creds is None:
            msg = "Deriv credentials required for connect()"
            raise DerivConnectionError(msg)
        self._credentials = creds

        with self._api_lock:
            self._state = DerivConnectionState.CONNECTING
            url = creds.websocket_url()
            self._endpoint = creds.endpoint
            self._app_id = creds.app_id
            try:
                # Close any prior session before opening a new WebSocket.
                self._safe_close_unlocked()
                self._transport.open(url)
                # authorize — token never logged
                auth_resp = self._transport.request({"authorize": creds.api_token})
                if auth_resp.get("error"):
                    err = auth_resp["error"]
                    msg = f"authorize failed: {err.get('message', err)}"
                    raise DerivConnectionError(msg)
                auth = auth_resp.get("authorize")
                if not isinstance(auth, dict):
                    msg = "authorize response missing authorize object"
                    raise DerivConnectionError(msg)

                is_virtual = int(auth.get("is_virtual", 0))
                loginid = str(auth.get("loginid", ""))
                try:
                    self._live_lock.evaluate_is_virtual(is_virtual, loginid=loginid or None)
                except LiveAccountForbiddenError:
                    self._state = DerivConnectionState.BLOCKED_LIVE
                    self._safe_close_unlocked()
                    raise

                account = DerivAccountSnapshot(
                    loginid=loginid,
                    currency=str(auth.get("currency", "")),
                    balance=float(auth.get("balance", 0.0) or 0.0),
                    is_virtual=is_virtual,
                    email=str(auth.get("email", "") or ""),
                    fullname=str(auth.get("fullname", "") or ""),
                    country=str(auth.get("country", "") or ""),
                    scopes=[str(s) for s in (auth.get("scopes") or [])],
                )
                self._account = account
                self._state = DerivConnectionState.CONNECTED
                self._last_error = None
                log.info(
                    "deriv connected loginid={} is_virtual={} currency={}",
                    account.loginid,
                    account.is_virtual,
                    account.currency,
                )
                return account
            except LiveAccountForbiddenError:
                raise
            except Exception as exc:
                self._state = DerivConnectionState.ERROR
                self._last_error = str(exc)
                self._safe_close_unlocked()
                if isinstance(exc, DerivConnectionError):
                    raise
                msg = f"Deriv connect failed: {exc}"
                raise DerivConnectionError(msg) from exc

    def disconnect(self) -> None:
        """Close the WebSocket connection."""
        with self._api_lock:
            self._safe_close_unlocked()
            self._state = DerivConnectionState.DISCONNECTED
            self._account = None
            log.info("deriv disconnected")

    def status(self) -> DerivConnectionStatus:
        """Return connection status without exposing tokens."""
        with self._api_lock:
            return DerivConnectionStatus(
                state=self._state,
                endpoint=self._endpoint,
                app_id=self._app_id,
                loginid=self._account.loginid if self._account else None,
                is_virtual=self._account.is_virtual if self._account else None,
                currency=self._account.currency if self._account else None,
                balance=self._account.balance if self._account else None,
                last_error=self._last_error,
                live_lock_engaged=self._live_lock.engaged,
            )

    def account_info(self) -> DerivAccountSnapshot:
        """Refresh balance via official ``balance`` call (read-only)."""
        self._live_lock.assert_allowed()
        with self._api_lock:
            if self._state != DerivConnectionState.CONNECTED or self._account is None:
                msg = "not connected — call connect() first"
                raise DerivConnectionError(msg)
            resp = self._transport.request({"balance": 1})
            if resp.get("error"):
                err = resp["error"]
                msg = f"balance failed: {err.get('message', err)}"
                raise DerivConnectionError(msg)
            bal = resp.get("balance")
            if not isinstance(bal, dict):
                msg = "balance response missing balance object"
                raise DerivConnectionError(msg)
            updated = self._account.model_copy(
                update={
                    "balance": float(bal.get("balance", self._account.balance) or 0.0),
                    "currency": str(bal.get("currency", self._account.currency) or ""),
                    "loginid": str(bal.get("loginid", self._account.loginid) or ""),
                }
            )
            self._account = updated
            return updated

    def ping(self) -> bool:
        """Send official ``ping``; returns True when ``pong`` received."""
        self._live_lock.assert_allowed()
        with self._api_lock:
            if self._state != DerivConnectionState.CONNECTED:
                msg = "not connected — call connect() first"
                raise DerivConnectionError(msg)
            resp = self._transport.request({"ping": 1})
            return resp.get("ping") == "pong"

    def _safe_close_unlocked(self) -> None:
        with contextlib.suppress(Exception):
            self._transport.close()


def ensure_no_order_apis(method_names: list[str]) -> None:
    """Guardrail: public client must not expose buy/sell/order helpers."""
    forbidden = {"buy", "sell", "proposal", "order_send", "place_order", "cashier"}
    found = forbidden.intersection(method_names)
    if found:
        msg = f"forbidden order-related methods exposed: {sorted(found)}"
        raise AssertionError(msg)
