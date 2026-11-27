"""Strategy engine — signal generation, causality, no orders."""

from __future__ import annotations

import inspect

import pandas as pd
import pytest

from quant_deriv_ai.agents.base import AgentContext
from quant_deriv_ai.core.event_bus import EventBus
from quant_deriv_ai.strategies.agent import StrategyAgent
from quant_deriv_ai.strategies.engine import StrategyEngine, StrategyEngineError
from quant_deriv_ai.strategies.models import SignalType
from quant_deriv_ai.strategies.registry import instantiate, strategy_ids
from tests.conftest_ta import make_ohlc


def test_engine_evaluate_all_strategies_produce_signals() -> None:
    frame = make_ohlc(250, seed=7)
    engine = StrategyEngine()
    for sid in strategy_ids():
        snap = engine.evaluate(sid, frame, symbol="EURUSD", timeframe="H1")
        assert snap.strategy_id == sid
        assert snap.bar_count == 250
        assert snap.latest is not None
        assert snap.latest.signal in {
            SignalType.BUY,
            SignalType.SELL,
            SignalType.HOLD,
            SignalType.EXIT,
        }
        assert snap.meta["no_orders"] is True
        assert snap.meta["auto_activate"] is False
        assert snap.meta["live_allowed"] is False
        assert snap.meta["edge_demonstrated"] is False


def test_signal_series_length_and_warmup_hold() -> None:
    frame = make_ohlc(80, seed=3)
    strategy = instantiate("STR-001")
    series = strategy.generate(frame, symbol="X", timeframe="M15")
    assert len(series) == len(frame)
    # Warmup before slow SMA ready should be HOLD
    assert all(s.signal is SignalType.HOLD for s in series[:29])


def test_prefix_stability_no_look_ahead() -> None:
    """Extending the series must not change past signals (causality)."""
    full = make_ohlc(200, seed=11)
    prefix = full.iloc[:150].copy()
    strategy = instantiate("STR-006")  # donchian breakout uses prior channel
    a = strategy.generate(prefix, symbol="S", timeframe="H1")
    b = strategy.generate(full, symbol="S", timeframe="H1")
    for i in range(len(a)):
        assert a[i].signal == b[i].signal, f"lookahead at bar {i}"


def test_future_mutation_independence() -> None:
    """Mutating future bars must not change signals at earlier indexes."""
    frame = make_ohlc(180, seed=19)
    strategy = instantiate("STR-004")
    base = strategy.generate(frame, symbol="S", timeframe="H1")
    mutated = frame.copy()
    mutated.loc[mutated.index[-20]:, "close"] = mutated.loc[
        mutated.index[-20]:, "close"
    ] * 1.5
    mutated.loc[mutated.index[-20]:, "high"] = mutated.loc[
        mutated.index[-20]:, "high"
    ] * 1.5
    alt = strategy.generate(mutated, symbol="S", timeframe="H1")
    cutoff = len(frame) - 20
    for i in range(cutoff):
        assert base[i].signal == alt[i].signal, f"future leak at {i}"


def test_evaluate_many() -> None:
    frame = make_ohlc(120, seed=2)
    engine = StrategyEngine()
    snaps = engine.evaluate_many(
        frame, symbol="EURUSD", timeframe="H1", keys=["STR-001", "STR-003"]
    )
    assert len(snaps) == 2
    assert {s.strategy_id for s in snaps} == {"STR-001", "STR-003"}


def test_empty_frame_raises() -> None:
    engine = StrategyEngine()
    with pytest.raises(StrategyEngineError, match="empty"):
        engine.evaluate("STR-001", pd.DataFrame())


def test_engine_has_no_order_methods() -> None:
    methods = [name for name, _ in inspect.getmembers(StrategyEngine, predicate=inspect.isfunction)]
    for name in methods:
        lower = name.lower()
        assert "order" not in lower
        assert "place" not in lower
        assert not lower.startswith("execute_trade")
        assert "go_live" not in lower
        assert "activate_live" not in lower


def test_strategy_agent_list_and_evaluate() -> None:
    bus = EventBus()
    engine = StrategyEngine()
    ctx = AgentContext(name="strat", bus=bus, config={"action": "list"})
    agent = StrategyAgent(ctx, engine)
    agent.start()
    assert agent.last_result is not None
    assert len(agent.last_result["strategies"]) == 12
    agent.stop()

    frame = make_ohlc(100, seed=5)
    ctx2 = AgentContext(
        name="strat2",
        bus=bus,
        config={
            "action": "evaluate",
            "strategy": "STR-002",
            "frame": frame,
            "symbol": "EURUSD",
            "timeframe": "H1",
        },
    )
    agent2 = StrategyAgent(ctx2, engine)
    agent2.start()
    assert agent2.last_result is not None
    assert agent2.last_result["strategy_id"] == "STR-002"
    assert agent2.last_result["meta"]["no_orders"] is True
    agent2.stop()


def test_all_signal_types_reachable() -> None:
    """Across strategies + seeds, all four SignalType values appear at least once."""
    seen: set[SignalType] = set()
    engine = StrategyEngine(include_series=True)
    for seed in (1, 2, 3, 5, 8, 13, 21):
        frame = make_ohlc(300, seed=seed)
        for sid in strategy_ids():
            snap = engine.evaluate(sid, frame, symbol="S", timeframe="H1", include_series=True)
            for sig in snap.series:
                seen.add(sig.signal)
            if len(seen) == 4:
                break
        if len(seen) == 4:
            break
    assert seen == {
        SignalType.BUY,
        SignalType.SELL,
        SignalType.HOLD,
        SignalType.EXIT,
    }
