"""CLI tests for ``quant mt5`` subcommands (mocked connector)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from quant_deriv_ai.cli.app import app
from quant_deriv_ai.execution.mt5.models import AccountSnapshot, PositionInfo

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[1]


def test_mt5_help() -> None:
    result = runner.invoke(app, ["mt5", "--help"])
    assert result.exit_code == 0
    for cmd in ("connect", "status", "account", "symbols", "positions", "disconnect"):
        assert cmd in result.stdout


def test_mt5_status_disconnected() -> None:
    result = runner.invoke(app, ["mt5", "status"])
    assert result.exit_code == 0
    assert "disconnected" in result.stdout


def test_mt5_connect_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MT5_LOGIN", "123")
    monkeypatch.setenv("MT5_PASSWORD", "secret")
    monkeypatch.setenv("MT5_SERVER", "Deriv-Demo")
    monkeypatch.setenv("QUANT_CONFIG_PATH", str(ROOT / "config" / "default.yaml"))

    account = AccountSnapshot(
        login=123,
        trade_mode=0,
        trade_mode_label="demo",
        balance=1000.0,
        equity=1000.0,
        margin=0.0,
        margin_free=1000.0,
        margin_level=0.0,
        profit=0.0,
        currency="USD",
        server="Deriv-Demo",
        company="Deriv",
    )
    mock_client = MagicMock()
    mock_client.connect.return_value = account

    with patch("quant_deriv_ai.cli.mt5_cmds._get_client", return_value=mock_client):
        result = runner.invoke(app, ["mt5", "connect"])
    assert result.exit_code == 0
    assert "Deriv-Demo" in result.stdout
    assert "secret" not in result.stdout
    mock_client.connect.assert_called_once()


def test_mt5_disconnect_mocked() -> None:
    mock_client = MagicMock()
    with patch("quant_deriv_ai.cli.mt5_cmds._get_client", return_value=mock_client):
        result = runner.invoke(app, ["mt5", "disconnect"])
    assert result.exit_code == 0
    mock_client.disconnect.assert_called_once()


def test_mt5_positions_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MT5_LOGIN", "123")
    monkeypatch.setenv("MT5_PASSWORD", "secret")
    monkeypatch.setenv("MT5_SERVER", "Deriv-Demo")
    monkeypatch.setenv("QUANT_CONFIG_PATH", str(ROOT / "config" / "default.yaml"))

    mock_client = MagicMock()
    mock_client.state.value = "connected"
    mock_client.positions.return_value = [
        PositionInfo(
            ticket=1,
            symbol="EURUSD",
            type=0,
            volume=0.1,
            price_open=1.1,
            price_current=1.11,
            profit=1.0,
        )
    ]
    with patch("quant_deriv_ai.cli.mt5_cmds._get_client", return_value=mock_client):
        result = runner.invoke(app, ["mt5", "positions"])
    assert result.exit_code == 0
    assert "EURUSD" in result.stdout
