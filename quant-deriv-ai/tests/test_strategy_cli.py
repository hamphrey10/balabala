"""CLI: quant strategy list|inspect|validate."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from quant_deriv_ai.cli.app import app

runner = CliRunner()


def test_strategy_help() -> None:
    result = runner.invoke(app, ["strategy", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "inspect" in result.output
    assert "validate" in result.output


def test_strategy_list_json() -> None:
    result = runner.invoke(app, ["strategy", "list", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload) == 12
    assert all(item["status"] == "hypothesis" for item in payload)
    assert all(item["auto_activate"] is False for item in payload)
    assert all(item["live_allowed"] is False for item in payload)
    assert all(item["edge_demonstrated"] is False for item in payload)


def test_strategy_inspect_json() -> None:
    result = runner.invoke(app, ["strategy", "inspect", "STR-001", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["id"] == "STR-001"
    assert payload["name"] == "sma_crossover"
    assert payload["activatable"] is False
    assert payload["safety"]["no_orders"] is True


def test_strategy_validate_ok() -> None:
    result = runner.invoke(
        app,
        ["strategy", "validate", "sma_crossover", "-p", "fast=8", "-p", "slow=21", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["params"]["fast"] == 8
    assert payload["params"]["slow"] == 21
    assert payload["no_orders"] is True
    assert payload["auto_activate"] is False


def test_strategy_validate_bad_param() -> None:
    result = runner.invoke(app, ["strategy", "validate", "STR-001", "-p", "nope=1"])
    assert result.exit_code == 1


def test_strategy_inspect_unknown() -> None:
    result = runner.invoke(app, ["strategy", "inspect", "STR-999"])
    assert result.exit_code == 1
