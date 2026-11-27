"""Unit tests for Deriv credential loading (never log tokens)."""

from __future__ import annotations

from pathlib import Path

import pytest

from quant_deriv_ai.core.exceptions import ConfigError
from quant_deriv_ai.execution.deriv.constants import DEFAULT_DERIV_ENDPOINT
from quant_deriv_ai.execution.deriv.credentials import load_credentials_from_env


def test_load_deriv_credentials_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DERIV_APP_ID", "1089")
    monkeypatch.setenv("DERIV_API_TOKEN", "secret-token-xyz")
    monkeypatch.setenv("DERIV_ENDPOINT", "wss://ws.derivws.com/websockets/v3")
    creds = load_credentials_from_env()
    assert creds is not None
    assert creds.app_id == "1089"
    assert "app_id=1089" in creds.websocket_url()
    safe = creds.safe_dict()
    assert safe["api_token"] == "***REDACTED***"
    assert "secret-token-xyz" not in str(safe)


def test_load_deriv_credentials_from_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DERIV_APP_ID", raising=False)
    monkeypatch.delenv("DERIV_API_TOKEN", raising=False)
    monkeypatch.delenv("DERIV_ENDPOINT", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DERIV_APP_ID=9999\nDERIV_API_TOKEN=from-file-token\n",
        encoding="utf-8",
    )
    creds = load_credentials_from_env(env_file=env_file)
    assert creds is not None
    assert creds.app_id == "9999"
    assert creds.endpoint == DEFAULT_DERIV_ENDPOINT
    assert "from-file-token" not in str(creds.safe_dict())


def test_load_deriv_credentials_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DERIV_APP_ID", "1089")
    monkeypatch.setenv("DERIV_API_TOKEN", "")
    with pytest.raises(ConfigError, match="incomplete"):
        load_credentials_from_env(env_file=Path("/dev/null"))


def test_load_deriv_credentials_missing_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DERIV_APP_ID", raising=False)
    monkeypatch.delenv("DERIV_API_TOKEN", raising=False)
    assert load_credentials_from_env(require_complete=False, env_file=Path("/dev/null")) is None
