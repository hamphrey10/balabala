"""CLI: quant research stats|edge|report."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from quant_deriv_ai.cli.app import app
from quant_deriv_ai.market_data.models import SeriesKind
from quant_deriv_ai.persistence.store import MarketDataStore
from tests.conftest_ta import make_ohlc

runner = CliRunner()


def _seed_store(tmp_path: Path) -> Path:
    store = MarketDataStore(tmp_path)
    frame = make_ohlc(200, seed=8)
    store.write_working(frame, symbol="EURUSD", kind=SeriesKind.CANDLES, timeframe="H1")
    return tmp_path


def test_research_help() -> None:
    result = runner.invoke(app, ["research", "--help"])
    assert result.exit_code == 0
    assert "stats" in result.output
    assert "edge" in result.output
    assert "report" in result.output


def test_research_stats_json(tmp_path: Path) -> None:
    root = _seed_store(tmp_path)
    result = runner.invoke(
        app,
        [
            "research",
            "stats",
            "-s",
            "EURUSD",
            "-t",
            "H1",
            "--data-root",
            str(root),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "EURUSD" in result.output
    assert "no_orders" in result.output


def test_research_edge_json(tmp_path: Path) -> None:
    root = _seed_store(tmp_path)
    result = runner.invoke(
        app,
        [
            "research",
            "edge",
            "-s",
            "EURUSD",
            "-t",
            "H1",
            "--data-root",
            str(root),
            "--lag",
            "1",
            "--probe",
            "momentum_sign",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "edge_probes" in result.output
    assert "causality" in result.output


def test_research_report_file(tmp_path: Path) -> None:
    root = _seed_store(tmp_path)
    out = tmp_path / "research.md"
    result = runner.invoke(
        app,
        [
            "research",
            "report",
            "-s",
            "EURUSD",
            "-t",
            "H1",
            "--data-root",
            str(root),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "Research Report" in text
    assert "no orders" in text.lower() or "No orders" in text
