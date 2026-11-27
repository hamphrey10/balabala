"""CLI: quant analyze technical / quant indicators list|validate."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from quant_deriv_ai.cli.app import app
from quant_deriv_ai.market_data.models import SeriesKind
from quant_deriv_ai.persistence.store import MarketDataStore
from tests.conftest_ta import make_ohlc

runner = CliRunner()


def test_indicators_list() -> None:
    result = runner.invoke(app, ["indicators", "list"])
    assert result.exit_code == 0, result.output
    for name in ("sma", "ema", "rsi", "macd", "atr", "bollinger"):
        assert name in result.output


def test_indicators_validate_ok() -> None:
    result = runner.invoke(app, ["indicators", "validate", "rsi", "--param", "period=21"])
    assert result.exit_code == 0, result.output
    assert "ok" in result.output.lower()


def test_indicators_validate_bad() -> None:
    result = runner.invoke(app, ["indicators", "validate", "nope"])
    assert result.exit_code == 1


def test_analyze_technical_from_store(tmp_path: Path) -> None:
    store = MarketDataStore(tmp_path)
    frame = make_ohlc(180, seed=3)
    store.write_working(frame, symbol="EURUSD", kind=SeriesKind.CANDLES, timeframe="H1")
    result = runner.invoke(
        app,
        [
            "analyze",
            "technical",
            "--symbol",
            "EURUSD",
            "--timeframe",
            "H1",
            "--data-root",
            str(tmp_path),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "EURUSD" in result.output
    assert "indicators" in result.output


def test_analyze_help() -> None:
    result = runner.invoke(app, ["analyze", "--help"])
    assert result.exit_code == 0
    assert "technical" in result.output


def test_indicators_help() -> None:
    result = runner.invoke(app, ["indicators", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "validate" in result.output
