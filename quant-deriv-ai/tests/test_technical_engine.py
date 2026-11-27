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
from quant_deriv_ai.technical.mtf import analyze_mtf
from quant_deriv_ai.technical.structure import detect_swings, support_resistance_from_swings
from quant_deriv_ai.technical.trend import classify_trend
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


def test_short_series_trend_is_unknown() -> None:
    """Insufficient SMA history must stay UNKNOWN, not SIDEWAYS."""
    n = 10  # less than default slow SMA(50)
    close = pd.Series([100.0 + i * 0.1 for i in range(n)])
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
        }
    )
    state = classify_trend(frame, fast=20, slow=50)
    assert state.direction is TrendDirection.UNKNOWN
    assert state.strength == 0.0


def test_engine_uppercase_indicator_name(frame: pd.DataFrame) -> None:
    engine = TechnicalAnalysisEngine()
    snap = engine.analyze(
        frame,
        symbol="CASE",
        timeframe="H1",
        indicators=["RSI", "SMA"],
    )
    assert any(k.startswith("rsi") for k in snap.indicators)
    assert any(k.startswith("sma") for k in snap.indicators)


def test_mtf_uses_engine_trend_params(frame: pd.DataFrame) -> None:
    """MTF classify_trend must honor engine SMA / swing settings."""
    engine = TechnicalAnalysisEngine(sma_fast=5, sma_slow=10, swing_left=1, swing_right=1)
    mtf_frames = {"H1": frame, "H4": frame.iloc[::4].reset_index(drop=True)}
    snap = engine.analyze(frame, symbol="MTF", timeframe="H1", mtf_frames=mtf_frames)
    assert snap.mtf is not None
    # Direct call with matching params should be consistent with engine path.
    direct = analyze_mtf(
        mtf_frames,
        sma_fast=5,
        sma_slow=10,
        swing_left=1,
        swing_right=1,
    )
    assert snap.mtf.dominant_trend == direct.dominant_trend
    assert [v.trend for v in snap.mtf.views] == [v.trend for v in direct.views]


def test_mtf_unknown_blocks_alignment() -> None:
    """Any requested TF that stays UNKNOWN must keep aligned=False."""
    long = make_ohlc(120, seed=5)
    short = make_ohlc(8, seed=6)  # too short for default SMA 20/50
    consensus = analyze_mtf(
        {"H1": long, "M5": short},
        sma_fast=20,
        sma_slow=50,
    )
    trends = {v.timeframe: v.trend for v in consensus.views}
    assert trends["M5"] is TrendDirection.UNKNOWN
    assert consensus.aligned is False
    assert "UNKNOWN" in consensus.notes
    assert "M5" in consensus.notes
