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


def test_mt5_status_survives_missing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """status/disconnect must not crash when YAML config is missing (Bugbot)."""
    import quant_deriv_ai.cli.mt5_cmds as mt5_cmds

    monkeypatch.setattr(mt5_cmds, "_client", None)
    monkeypatch.setenv("QUANT_CONFIG_PATH", "/nonexistent/quant-config.yaml")
    result = runner.invoke(app, ["mt5", "status"])
    assert result.exit_code == 0, result.stdout
    assert "disconnected" in result.stdout

    monkeypatch.setattr(mt5_cmds, "_client", None)
    result = runner.invoke(app, ["mt5", "disconnect"])
    assert result.exit_code == 0, result.stdout
    assert "disconnected" in result.stdout.lower()


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


def test_mt5_connect_passes_config_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """YAML mt5.* settings must reach Mt5Client on construct (Bugbot MEDIUM)."""
    import quant_deriv_ai.cli.mt5_cmds as mt5_cmds

    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        """
app:
  name: quant-deriv-ai
  environment: development
  log_level: INFO
trading:
  mode: demo
  allow_live: false
risk:
  capital_preservation_priority: true
  martingale_forbidden: true
  aggressive_loss_recovery_forbidden: true
  require_demonstrated_edge: true
  abstain_without_edge: true
mt5:
  enabled: false
  terminal_path: "C:\\\\Custom\\\\terminal64.exe"
  timeout_ms: 12345
  max_retries: 7
  backoff_base_s: 1.5
  heartbeat_interval_s: 42
logging:
  structured: true
  serialize: false
  sink: stderr
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("QUANT_CONFIG_PATH", str(cfg_path))
    monkeypatch.setenv("MT5_LOGIN", "123")
    monkeypatch.setenv("MT5_PASSWORD", "secret")
    monkeypatch.setenv("MT5_SERVER", "Deriv-Demo")
    monkeypatch.delenv("MT5_PATH", raising=False)
    monkeypatch.setattr(mt5_cmds, "_client", None)

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
    mock_instance = MagicMock()
    mock_instance.connect.return_value = account

    with patch("quant_deriv_ai.cli.mt5_cmds.Mt5Client", return_value=mock_instance) as ctor:
        result = runner.invoke(app, ["mt5", "connect"])

    assert result.exit_code == 0, result.stdout
    ctor.assert_called_once()
    kwargs = ctor.call_args.kwargs
    assert kwargs["timeout_ms"] == 12345
    assert kwargs["max_retries"] == 7
    assert kwargs["backoff_base_s"] == 1.5
    assert kwargs["heartbeat_interval_s"] == 42
    connect_creds = mock_instance.connect.call_args.args[0]
    assert connect_creds.terminal_path.endswith("terminal64.exe")
    assert "secret" not in result.stdout


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
