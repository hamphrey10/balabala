"""CLI tests for ``quant deriv`` subcommands (mocked connector)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from quant_deriv_ai.cli.app import app
from quant_deriv_ai.execution.deriv.models import DerivAccountSnapshot

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[1]


def test_deriv_help() -> None:
    result = runner.invoke(app, ["deriv", "--help"])
    assert result.exit_code == 0
    for cmd in ("connect", "status", "account", "disconnect"):
        assert cmd in result.stdout


def test_deriv_status_disconnected(monkeypatch: pytest.MonkeyPatch) -> None:
    import quant_deriv_ai.cli.deriv_cmds as deriv_cmds

    monkeypatch.setattr(deriv_cmds, "_client", None)
    monkeypatch.setenv("QUANT_CONFIG_PATH", str(ROOT / "config" / "default.yaml"))
    result = runner.invoke(app, ["deriv", "status"])
    assert result.exit_code == 0
    assert "disconnected" in result.stdout


def test_deriv_connect_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DERIV_APP_ID", "1089")
    monkeypatch.setenv("DERIV_API_TOKEN", "secret-token")
    monkeypatch.setenv("QUANT_CONFIG_PATH", str(ROOT / "config" / "default.yaml"))

    account = DerivAccountSnapshot(
        loginid="VRTC1",
        currency="USD",
        balance=5000.0,
        is_virtual=1,
        scopes=["read"],
    )
    mock_client = MagicMock()
    mock_client.connect.return_value = account

    with patch("quant_deriv_ai.cli.deriv_cmds._get_client", return_value=mock_client):
        result = runner.invoke(app, ["deriv", "connect"])
    assert result.exit_code == 0
    assert "VRTC1" in result.stdout
    assert "secret-token" not in result.stdout
    mock_client.connect.assert_called_once()


def test_deriv_disconnect_mocked() -> None:
    mock_client = MagicMock()
    with patch("quant_deriv_ai.cli.deriv_cmds._get_client", return_value=mock_client):
        result = runner.invoke(app, ["deriv", "disconnect"])
    assert result.exit_code == 0
    mock_client.disconnect.assert_called_once()
