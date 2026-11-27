"""CLI smoke tests via Typer's CliRunner."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from quant_deriv_ai import __version__
from quant_deriv_ai.cli.app import app
from quant_deriv_ai.cli.doctor import doctor_passed, run_doctor

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_config_validate() -> None:
    root = Path(__file__).resolve().parents[1]
    result = runner.invoke(app, ["config", "validate", "-c", str(root / "config" / "default.yaml")])
    assert result.exit_code == 0
    assert "config valid" in result.stdout


def test_status() -> None:
    root = Path(__file__).resolve().parents[1]
    result = runner.invoke(app, ["status", "-c", str(root / "config" / "default.yaml")])
    assert result.exit_code == 0
    assert "demo" in result.stdout


def test_doctor_runs() -> None:
    result = runner.invoke(app, ["doctor"])
    # Core deps should pass after install; exit 0 even if MT5 fails on Linux.
    assert result.exit_code == 0
    assert "quant doctor" in result.stdout or "doctor" in result.stdout.lower()


def test_doctor_helpers() -> None:
    results = run_doctor()
    assert any(r.name == "python" for r in results)
    assert any(r.name.startswith("mt5:") for r in results)
    # After editable install in CI/local, deps should be present.
    assert doctor_passed(results) is True
