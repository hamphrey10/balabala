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


def test_abstain_rate_excludes_warmup_nans() -> None:
    """Warmup NaNs must not inflate abstain_rate; reconcile with observations."""
    from quant_deriv_ai.quantitative.causality import forward_returns

    # len=12, lag=1, horizon=1 → fwd finite on indices 0..9
    close = pd.Series([100.0 + i for i in range(12)], dtype=float)
    # 3 warmup NaNs, 4 zeros, 3 actives, 2 trailing (fwd NaN)
    signal = pd.Series(
        [np.nan, np.nan, np.nan, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 0.0, 0.0],
        dtype=float,
    )
    metrics = evaluate_edge(
        signal,
        close,
        probe_name="abstain",
        forward_lag=1,
        forward_horizon=1,
        min_observations=1,
    )
    # Eligible defined+fwd: indices 3..9 → obs=7, active=3, abstain=4
    assert metrics.observations == 7
    assert metrics.active_signals == 3
    assert metrics.abstain_rate == pytest.approx(4 / 7)
    abstain_count = metrics.observations - metrics.active_signals
    assert metrics.abstain_rate == pytest.approx(abstain_count / metrics.observations)

    fwd = forward_returns(close, lag=1, horizon=1)
    naive = float(((signal.isna() | (signal == 0.0)) & fwd.notna()).mean())
    assert metrics.abstain_rate < naive


def test_sharpe_not_annualized() -> None:
    """Sparse active-signal Sharpe is mean/std — no sqrt(252) scale-up."""
    close = pd.Series(np.linspace(100.0, 120.0, 40))
    # Alternating +1 so most bars are active
    signal = pd.Series([1.0 if i % 2 == 0 else -1.0 for i in range(40)])
    metrics = evaluate_edge(
        signal,
        close,
        probe_name="sharpe",
        forward_lag=1,
        min_observations=5,
    )
    assert metrics.sharpe is not None
    # If annualized with 252, |sharpe| would typically be >> 1 for any nonzero mean/std
    # Per-trade sharpe magnitude for this synthetic series stays modest.
    assert abs(metrics.sharpe) < 5.0
    assert "not calendar-annualized" in metrics.notes


def test_max_drawdown_seeds_zero_peak() -> None:
    from quant_deriv_ai.quantitative.edge import _max_drawdown

    # Path starts with losses: without seeding 0, HWM would be first negative equity
    # and max DD would understate the drop from capital=0.
    pnl = np.array([-0.10, -0.05, 0.02], dtype=float)
    dd = _max_drawdown(pnl)
    assert dd is not None
    # Equity: 0 → -0.10 → -0.15 → -0.13; peak stays 0; min DD = -0.15
    assert dd == pytest.approx(-0.15)
