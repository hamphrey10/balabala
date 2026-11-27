"""Unit tests for secure MT5 credential loading."""

from __future__ import annotations

from pathlib import Path

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


def test_load_credentials_from_dotenv_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``.env`` values must work without shell exports (Bugbot HIGH)."""
    monkeypatch.delenv("MT5_LOGIN", raising=False)
    monkeypatch.delenv("MT5_PASSWORD", raising=False)
    monkeypatch.delenv("MT5_SERVER", raising=False)
    monkeypatch.delenv("MT5_PATH", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MT5_LOGIN=87654321\n"
        "MT5_PASSWORD=from-dotenv-secret\n"
        "MT5_SERVER=Deriv-Demo\n"
        "MT5_PATH=C:\\\\MT5\\\\terminal64.exe\n",
        encoding="utf-8",
    )
    creds = load_credentials_from_env(env_file=env_file)
    assert creds is not None
    assert creds.login == 87654321
    assert creds.server == "Deriv-Demo"
    assert creds.terminal_path.endswith("terminal64.exe")
    safe = creds.safe_dict()
    assert safe["password"] == "***REDACTED***"
    assert "from-dotenv-secret" not in str(safe)


def test_load_credentials_env_overrides_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MT5_LOGIN=111\nMT5_PASSWORD=file-secret\nMT5_SERVER=File-Server\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MT5_LOGIN", "222")
    monkeypatch.setenv("MT5_PASSWORD", "env-secret")
    monkeypatch.setenv("MT5_SERVER", "Env-Server")
    creds = load_credentials_from_env(env_file=env_file)
    assert creds is not None
    assert creds.login == 222
    assert creds.server == "Env-Server"
    assert "file-secret" not in creds.safe_dict().values()


def test_load_credentials_missing_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MT5_LOGIN", raising=False)
    monkeypatch.delenv("MT5_PASSWORD", raising=False)
    monkeypatch.delenv("MT5_SERVER", raising=False)
    # Isolate from any ambient .env in the checkout cwd.
    empty = Path("/dev/null")
    assert load_credentials_from_env(require_complete=False, env_file=empty) is None


def test_load_credentials_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MT5_LOGIN", "1")
    monkeypatch.setenv("MT5_PASSWORD", "")
    monkeypatch.setenv("MT5_SERVER", "Deriv-Demo")
    with pytest.raises(ConfigError, match="incomplete"):
        load_credentials_from_env()
