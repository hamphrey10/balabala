"""QuantitativeResearchEngine + agent + report writer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from quant_deriv_ai.agents.base import AgentContext
from quant_deriv_ai.core.event_bus import EventBus
from quant_deriv_ai.market_data.models import SeriesKind
from quant_deriv_ai.persistence.store import MarketDataStore
from quant_deriv_ai.quantitative.agent import QuantitativeResearchAgent
from quant_deriv_ai.quantitative.engine import QuantitativeResearchEngine
from quant_deriv_ai.quantitative.models import CausalityStatus, EdgeVerdict
from quant_deriv_ai.quantitative.reports import render_markdown, write_report
from tests.conftest_ta import make_ohlc


@pytest.fixture
def frame() -> pd.DataFrame:
    return make_ohlc(250, seed=21)


def test_stats_report_fields(frame: pd.DataFrame) -> None:
    engine = QuantitativeResearchEngine()
    report = engine.stats(frame, symbol="SYNTH", timeframe="H1")
    assert report.symbol == "SYNTH"
    assert report.bar_count == len(frame)
    assert report.returns is not None
    assert report.price_stats is not None
    assert report.meta.get("no_orders") is True
    assert report.edge_probes == []


def test_edge_probes_and_causality(frame: pd.DataFrame) -> None:
    engine = QuantitativeResearchEngine(edge_min_observations=20)
    report = engine.edge(frame, symbol="SYNTH", timeframe="H1")
    assert len(report.edge_probes) == 2
    assert all(e.forward_lag >= 1 for e in report.edge_probes)
    assert all(e.verdict in set(EdgeVerdict) for e in report.edge_probes)
    assert report.causality
    assert all(c.status is not CausalityStatus.FAIL for c in report.causality)
    assert "no orders" in report.summary.lower()


def test_report_write_markdown(frame: pd.DataFrame, tmp_path: Path) -> None:
    engine = QuantitativeResearchEngine()
    out = tmp_path / "r.md"
    report = engine.report(frame, symbol="X", timeframe="M15", output_path=out, fmt="markdown")
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "Research Report" in text
    assert "Edge probes" in text
    assert "Causality" in text
    md = render_markdown(report)
    assert report.symbol in md


def test_report_write_json(frame: pd.DataFrame, tmp_path: Path) -> None:
    engine = QuantitativeResearchEngine()
    report = engine.stats(frame, symbol="Y", timeframe="H1")
    path = write_report(report, tmp_path / "r.json", fmt="json")
    assert path.is_file()
    assert "Y" in path.read_text(encoding="utf-8")


def test_from_store(tmp_path: Path) -> None:
    store = MarketDataStore(tmp_path)
    frame = make_ohlc(180, seed=4)
    store.write_working(frame, symbol="EURUSD", kind=SeriesKind.CANDLES, timeframe="H1")
    engine = QuantitativeResearchEngine(reports_dir=str(tmp_path / "reports"))
    stats = engine.stats_from_store(tmp_path, symbol="EURUSD", timeframe="H1")
    assert stats.bar_count == 180
    report = engine.report_from_store(
        tmp_path,
        symbol="EURUSD",
        timeframe="H1",
        output_path=tmp_path / "out.md",
    )
    assert (tmp_path / "out.md").is_file()
    assert report.meta.get("report_path")


def test_agent_stats_action(frame: pd.DataFrame) -> None:
    engine = QuantitativeResearchEngine()
    ctx = AgentContext(
        name="qr",
        bus=EventBus(),
        config={"action": "stats", "frame": frame, "symbol": "Z", "timeframe": "H1"},
    )
    agent = QuantitativeResearchAgent(ctx, engine)
    agent.start()
    assert agent.last_result is not None
    assert agent.last_result["symbol"] == "Z"
    assert agent.last_result["meta"]["no_orders"] is True
    agent.stop()


def test_unknown_probe_raises(frame: pd.DataFrame) -> None:
    engine = QuantitativeResearchEngine()
    with pytest.raises(Exception, match="unknown edge probe"):
        engine.edge(frame, symbol="X", timeframe="H1", probes=["not_a_probe"])
