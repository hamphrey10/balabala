"""Deriv WebSocket transport — official JSON request/response over websockets."""

from __future__ import annotations

import contextlib
import json
import threading
from typing import Any, Protocol

from quant_deriv_ai.core.exceptions import DerivConnectionError


class DerivTransport(Protocol):
    """Minimal request/response transport (injectable for unit tests)."""

    def open(self, url: str) -> None: ...

    def request(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def close(self) -> None: ...


class WebsocketTransport:
    """Synchronous WebSocket client using the official ``websockets`` sync API.

    Sends one JSON object and waits for a matching ``req_id`` response.
    Never logs payload contents (may contain tokens).
    """

    def __init__(self, *, timeout_s: float = 30.0) -> None:
        self._timeout_s = timeout_s
        self._ws: Any | None = None
        self._req_id = 0
        self._lock = threading.RLock()

    def open(self, url: str) -> None:
        # Always drop any prior socket first — reconnect must not leak sessions.
        self.close()
        try:
            from websockets.sync.client import connect
        except ImportError as exc:
            msg = (
                "websockets package is required for Deriv API connections — "
                "install project dependencies (pip install -e .)"
            )
            raise DerivConnectionError(msg) from exc
        try:
            with self._lock:
                self._ws = connect(
                    url, open_timeout=self._timeout_s, close_timeout=self._timeout_s
                )
        except Exception as exc:  # noqa: BLE001
            msg = f"Deriv WebSocket open failed: {exc}"
            raise DerivConnectionError(msg) from exc

    def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self._ws is None:
                msg = "Deriv WebSocket is not open"
                raise DerivConnectionError(msg)
            self._req_id += 1
            req_id = self._req_id
            body = dict(payload)
            body["req_id"] = req_id
            try:
                self._ws.send(json.dumps(body))
                while True:
                    raw = self._ws.recv(timeout=self._timeout_s)
                    data = json.loads(raw)
                    if not isinstance(data, dict):
                        continue
                    if data.get("req_id") == req_id:
                        return data
            except DerivConnectionError:
                raise
            except Exception as exc:  # noqa: BLE001
                msg = f"Deriv WebSocket request failed: {exc}"
                raise DerivConnectionError(msg) from exc

    def close(self) -> None:
        with self._lock:
            if self._ws is not None:
                with contextlib.suppress(Exception):
                    self._ws.close()
                self._ws = None
