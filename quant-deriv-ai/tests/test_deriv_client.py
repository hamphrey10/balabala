"""Unit tests for DerivClient with a fake transport (no real WebSocket)."""

from __future__ import annotations

from typing import Any

import pytest

from quant_deriv_ai.core.exceptions import DerivConnectionError, LiveAccountForbiddenError
from quant_deriv_ai.execution.deriv.client import DerivClient, ensure_no_order_apis
from quant_deriv_ai.execution.deriv.credentials import DerivCredentials
from quant_deriv_ai.execution.deriv.live_lock import DerivLiveLock


class FakeTransport:
    def __init__(self, *, is_virtual: int = 1) -> None:
        self.is_virtual = is_virtual
        self.opened: str | None = None
        self.closed = False
        self.requests: list[dict[str, Any]] = []

    def open(self, url: str) -> None:
        self.opened = url

    def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(dict(payload))
        if "authorize" in payload:
            # Never echo token back into assertions as a "logged" value.
            return {
                "authorize": {
                    "loginid": "VRTC12345",
                    "currency": "USD",
                    "balance": 10000.0,
                    "is_virtual": self.is_virtual,
                    "email": "demo@example.com",
                    "fullname": "Demo User",
                    "country": "id",
                    "scopes": ["read", "trade"],
                },
                "msg_type": "authorize",
            }
        if payload.get("balance") == 1:
            return {
                "balance": {
                    "balance": 10050.5,
                    "currency": "USD",
                    "loginid": "VRTC12345",
                },
                "msg_type": "balance",
            }
        if payload.get("ping") == 1:
            return {"ping": "pong", "msg_type": "ping"}
        return {"echo_req": payload}

    def close(self) -> None:
        self.closed = True


def _creds() -> DerivCredentials:
    return DerivCredentials(app_id="1089", api_token="test-token-not-for-log")


@pytest.mark.unit
def test_connect_demo_success() -> None:
    transport = FakeTransport(is_virtual=1)
    client = DerivClient(transport=transport)
    account = client.connect(_creds())
    assert account.loginid == "VRTC12345"
    assert account.is_demo is True
    assert client.state.value == "connected"
    assert transport.opened is not None
    assert "app_id=1089" in transport.opened
    # Token must not appear in status payload.
    status = client.status()
    assert "test-token" not in str(status.model_dump())


@pytest.mark.unit
def test_connect_real_account_locks() -> None:
    transport = FakeTransport(is_virtual=0)
    lock = DerivLiveLock()
    client = DerivClient(transport=transport, live_lock=lock)
    with pytest.raises(LiveAccountForbiddenError):
        client.connect(_creds())
    assert lock.engaged is True
    assert client.state.value == "blocked_live"
    with pytest.raises(LiveAccountForbiddenError):
        client.account_info()


@pytest.mark.unit
def test_account_info_and_ping() -> None:
    transport = FakeTransport(is_virtual=1)
    client = DerivClient(transport=transport)
    client.connect(_creds())
    account = client.account_info()
    assert account.balance == 10050.5
    assert client.ping() is True


@pytest.mark.unit
def test_disconnect() -> None:
    transport = FakeTransport()
    client = DerivClient(transport=transport)
    client.connect(_creds())
    client.disconnect()
    assert client.state.value == "disconnected"
    assert transport.closed is True
    with pytest.raises(DerivConnectionError):
        client.account_info()


@pytest.mark.unit
def test_no_order_methods_exposed() -> None:
    methods = [m for m in dir(DerivClient) if not m.startswith("_")]
    ensure_no_order_apis(methods)
    assert "buy" not in methods
    assert "sell" not in methods
    assert "connect" in methods
