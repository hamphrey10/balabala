"""Unit tests for secure MT5 credential loading."""

from __future__ import annotations

import pytest

from quant_deriv_ai.core.exceptions import ConfigError
from quant_deriv_ai.execution.mt5.credentials import load_credentials_from_env


def test_load_credentials_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MT5_LOGIN", "12345678")
    monkeypatch.setenv("MT5_PASSWORD", "secret-demo")
    monkeypatch.setenv("MT5_SERVER", "Deriv-Demo")
    monkeypatch.setenv("MT5_PATH", "C:\\MT5\\terminal64.exe")
    creds = load_credentials_from_env()
    assert creds is not None
    assert creds.login == 12345678
    assert creds.server == "Deriv-Demo"
    safe = creds.safe_dict()
    assert safe["password"] == "***REDACTED***"
    assert "secret-demo" not in str(safe)


def test_load_credentials_missing_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MT5_LOGIN", raising=False)
    monkeypatch.delenv("MT5_PASSWORD", raising=False)
    monkeypatch.delenv("MT5_SERVER", raising=False)
    assert load_credentials_from_env(require_complete=False) is None


def test_load_credentials_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MT5_LOGIN", "1")
    monkeypatch.setenv("MT5_PASSWORD", "")
    monkeypatch.setenv("MT5_SERVER", "Deriv-Demo")
    with pytest.raises(ConfigError, match="incomplete"):
        load_credentials_from_env()
