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


def test_deriv_connect_uses_yaml_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI must pass YAML deriv.endpoint into credentials when env unset."""
    import quant_deriv_ai.cli.deriv_cmds as deriv_cmds
    from quant_deriv_ai.execution.deriv.credentials import load_credentials_from_env

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
deriv:
  enabled: true
  endpoint: "wss://yaml-endpoint.example/websockets/v3"
  timeout_s: 12
mt5:
  enabled: false
  terminal_path: ""
  timeout_ms: 60000
  max_retries: 3
  backoff_base_s: 0.5
  heartbeat_interval_s: 30
logging:
  structured: true
  serialize: false
  sink: stderr
""",
        encoding="utf-8",
    )
    # Isolate EnvSettings from any ambient cwd `.env` (Bugbot LOW).
    monkeypatch.chdir(tmp_path)
    empty_env = Path("/dev/null")

    def _load_isolated(**kwargs: object) -> object:
        kwargs.setdefault("env_file", empty_env)
        return load_credentials_from_env(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(deriv_cmds, "load_credentials_from_env", _load_isolated)
    monkeypatch.setenv("QUANT_CONFIG_PATH", str(cfg_path))
    monkeypatch.setenv("DERIV_APP_ID", "1089")
    monkeypatch.setenv("DERIV_API_TOKEN", "secret-token")
    monkeypatch.delenv("DERIV_ENDPOINT", raising=False)

    account = DerivAccountSnapshot(
        loginid="VRTC1",
        currency="USD",
        balance=1.0,
        is_virtual=1,
        scopes=["read"],
    )
    mock_client = MagicMock()
    mock_client.connect.return_value = account

    with patch("quant_deriv_ai.cli.deriv_cmds._get_client", return_value=mock_client):
        result = runner.invoke(app, ["deriv", "connect"])
    assert result.exit_code == 0, result.stdout
    creds = mock_client.connect.call_args.args[0]
    assert creds.endpoint == "wss://yaml-endpoint.example/websockets/v3"
    assert "secret-token" not in result.stdout


def test_deriv_disconnect_mocked() -> None:
    mock_client = MagicMock()
    with patch("quant_deriv_ai.cli.deriv_cmds._get_client", return_value=mock_client):
        result = runner.invoke(app, ["deriv", "disconnect"])
    assert result.exit_code == 0
    mock_client.disconnect.assert_called_once()
