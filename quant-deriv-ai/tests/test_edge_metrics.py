"""Edge probe metrics + look-ahead rejection."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_deriv_ai.quantitative.causality import CausalityError
from quant_deriv_ai.quantitative.edge import (
    EdgeError,
    evaluate_edge,
    momentum_sign_probe,
    rsi_threshold_probe,
)
from quant_deriv_ai.quantitative.models import EdgeVerdict
from tests.conftest_ta import make_ohlc


def test_evaluate_edge_rejects_zero_lag() -> None:
    close = pd.Series([100.0, 101.0, 102.0, 103.0])
    signal = pd.Series([1.0, 1.0, 1.0, 1.0])
    with pytest.raises(CausalityError):
        evaluate_edge(signal, close, probe_name="x", forward_lag=0)


def test_same_bar_cheat_misaligned_with_lag1() -> None:
    """Same-bar sign(return) cannot be used with lag=0; lag=1 breaks the cheat."""
    close = pd.Series(np.cumprod(1.0 + np.array([0.0, 0.01, -0.02, 0.03, -0.01, 0.02, 0.01])))
    rets = close.pct_change()
    cheat = np.sign(rets).fillna(0.0)
    metrics = evaluate_edge(
        cheat,
        close,
        probe_name="cheat_same_bar",
        forward_lag=1,
        forward_horizon=1,
        min_observations=3,
    )
    assert metrics.active_signals >= 1
    assert metrics.hit_rate is not None
    assert metrics.hit_rate < 1.0


def test_momentum_probe_causal() -> None:
    frame = make_ohlc(120, seed=5)
    lookback = 5
    signal = momentum_sign_probe(frame["close"], lookback=lookback)
    assert signal.iloc[:lookback].isna().all()
    metrics = evaluate_edge(
        signal,
        frame["close"],
        probe_name="mom",
        forward_lag=1,
        min_observations=10,
    )
    assert metrics.forward_lag == 1
    assert metrics.verdict in set(EdgeVerdict)
    assert "Research probe" in metrics.notes


def test_rsi_threshold_probe_shape() -> None:
    frame = make_ohlc(150, seed=9)
    signal = rsi_threshold_probe(frame["close"], period=14, low=30, high=70)
    assert len(signal) == len(frame)
    assert set(np.unique(signal.dropna().to_numpy())).issubset({-1.0, 0.0, 1.0})


def test_length_mismatch() -> None:
    with pytest.raises(EdgeError):
        evaluate_edge(pd.Series([1.0, -1.0]), pd.Series([1.0, 2.0, 3.0]), probe_name="x")
