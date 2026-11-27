"""TechnicalAnalysisEngine + structure / MTF / volume caveats."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from quant_deriv_ai.agents.base import AgentContext
from quant_deriv_ai.core.event_bus import EventBus
from quant_deriv_ai.market_data.models import SeriesKind
from quant_deriv_ai.persistence.store import MarketDataStore
from quant_deriv_ai.technical.agent import TechnicalAnalysisAgent
from quant_deriv_ai.technical.engine import TechnicalAnalysisEngine
from quant_deriv_ai.technical.models import BreakoutSide, TrendDirection, VolumeCaveat
from quant_deriv_ai.technical.structure import detect_swings, support_resistance_from_swings
from tests.conftest_ta import make_ohlc


@pytest.fixture
def frame() -> pd.DataFrame:
    return make_ohlc(300, seed=11)


def test_snapshot_contains_expected_fields(frame: pd.DataFrame) -> None:
    engine = TechnicalAnalysisEngine(volume_is_synthetic=True)
    snap = engine.analyze(frame, symbol="SYNTH", timeframe="H1")
    assert snap.symbol == "SYNTH"
    assert snap.bar_count == len(frame)
    assert snap.last_close is not None
    assert "rsi_14" in snap.indicators or "rsi" in str(snap.indicators)
    # RSI series is named rsi_14 in core
    assert any(k.startswith("rsi") for k in snap.indicators)
    assert snap.trend.direction in set(TrendDirection)
    assert snap.volume.volume_is_synthetic is True
    assert "synthetic" in snap.volume.note.lower() or "liquidity" in snap.volume.note.lower()
    assert snap.meta.get("no_orders") is True


def test_volume_caveat_default_synthetic(frame: pd.DataFrame) -> None:
    engine = TechnicalAnalysisEngine()
    snap = engine.analyze(frame, symbol="X", timeframe="M15")
    assert isinstance(snap.volume, VolumeCaveat)
    assert snap.volume.volume_is_synthetic is True


def test_swings_and_sr(frame: pd.DataFrame) -> None:
    swings = detect_swings(frame["high"], frame["low"], left=2, right=2)
    assert len(swings) > 0
    levels = support_resistance_from_swings(swings)
    assert all(lvl.kind in {"support", "resistance"} for lvl in levels)


def test_breakout_none_on_flat() -> None:
    # Flat series → no breakout of prior channel by construction at last bar mid.
    n = 60
    close = pd.Series([100.0] * n)
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
        }
    )
    engine = TechnicalAnalysisEngine(breakout_lookback=20)
    snap = engine.analyze(frame, symbol="FLAT", timeframe="M5")
    assert snap.breakout.side is BreakoutSide.NONE


def test_mtf_consensus(frame: pd.DataFrame) -> None:
    engine = TechnicalAnalysisEngine()
    # Use two slices as stand-in for different TFs (independent frames).
    mtf = {"H1": frame, "H4": frame.iloc[::4].reset_index(drop=True)}
    snap = engine.analyze(frame, symbol="MTF", timeframe="H1", mtf_frames=mtf)
    assert snap.mtf is not None
    assert len(snap.mtf.views) == 2


def test_analyze_from_store(tmp_path: Path, frame: pd.DataFrame) -> None:
    store = MarketDataStore(tmp_path)
    store.write_working(frame, symbol="EURUSD", kind=SeriesKind.CANDLES, timeframe="H1")
    engine = TechnicalAnalysisEngine()
    snap = engine.analyze_from_store(tmp_path, symbol="EURUSD", timeframe="H1")
    assert snap.symbol == "EURUSD"
    assert snap.bar_count == len(frame)


def test_agent_analyze(frame: pd.DataFrame) -> None:
    engine = TechnicalAnalysisEngine()
    ctx = AgentContext(
        name="ta",
        bus=EventBus(),
        config={"action": "analyze", "frame": frame, "symbol": "S", "timeframe": "H1"},
    )
    agent = TechnicalAnalysisAgent(ctx, engine)
    agent.start()
    assert agent.last_result is not None
    assert agent.last_result["symbol"] == "S"
    agent.stop()


def test_agent_list_indicators() -> None:
    engine = TechnicalAnalysisEngine()
    ctx = AgentContext(name="ta", bus=EventBus(), config={"action": "list_indicators"})
    agent = TechnicalAnalysisAgent(ctx, engine)
    agent.start()
    assert agent.last_result is not None
    names = agent.last_result["indicators"]
    for required in ("sma", "ema", "rsi", "macd", "atr", "adx", "bollinger"):
        assert required in names
    agent.stop()


def test_engine_rejects_missing_ohlc() -> None:
    engine = TechnicalAnalysisEngine()
    with pytest.raises(Exception, match="OHLC"):
        engine.analyze(pd.DataFrame({"close": [1.0, 2.0]}), symbol="X", timeframe="M1")
