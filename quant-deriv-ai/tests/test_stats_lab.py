"""Stats lab unit tests — descriptive stats, returns, causality of rolling windows."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_deriv_ai.quantitative.causality import (
    CausalityError,
    assert_min_forward_lag,
    check_forward_return_ignores_signal_bar,
    check_future_mutation,
    check_prefix_stability,
    forward_returns,
)
from quant_deriv_ai.quantitative.models import CausalityStatus
from quant_deriv_ai.quantitative.stats_lab import (
    StatsLabError,
    autocorrelation,
    compute_returns,
    correlation_matrix,
    describe_series,
    rolling_mean,
    summarize_returns,
)
from tests.conftest_ta import make_ohlc


def test_compute_returns_log_and_simple() -> None:
    close = pd.Series([100.0, 110.0, 99.0])
    log_r = compute_returns(close, method="log")
    simple = compute_returns(close, method="simple")
    assert np.isnan(log_r.iloc[0])
    assert log_r.iloc[1] == pytest.approx(np.log(1.1))
    assert simple.iloc[1] == pytest.approx(0.1)


def test_compute_returns_bad_method() -> None:
    with pytest.raises(StatsLabError):
        compute_returns([1.0, 2.0], method="bogus")


def test_describe_series_moments() -> None:
    rng = np.random.default_rng(0)
    values = rng.normal(0.0, 1.0, size=500)
    stats = describe_series(values, name="x")
    assert stats.count == 500
    assert stats.mean is not None
    assert abs(stats.mean) < 0.2
    assert stats.std is not None
    assert 0.8 < stats.std < 1.2
    assert stats.skew is not None
    assert stats.kurtosis is not None


def test_rolling_mean_causal_prefix() -> None:
    series = pd.Series(np.arange(20, dtype=float))
    check = check_prefix_stability(lambda s: rolling_mean(s, 5), series)
    assert check.status is CausalityStatus.PASS


def test_rolling_mean_future_mutation() -> None:
    series = pd.Series(np.linspace(1.0, 2.0, 50))
    check = check_future_mutation(lambda s: rolling_mean(s, 5), series)
    assert check.status is CausalityStatus.PASS


def test_autocorrelation_lags() -> None:
    # Strong AR(1)
    rng = np.random.default_rng(1)
    n = 400
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = 0.8 * x[i - 1] + rng.normal(0, 0.1)
    points = autocorrelation(x, lags=(1, 2))
    assert points[0].value is not None
    assert points[0].value > 0.5


def test_correlation_matrix() -> None:
    frame = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [1.0, 2.0, 3.0]})
    corr = correlation_matrix(frame)
    assert corr.loc["a", "b"] == pytest.approx(1.0)


def test_summarize_returns() -> None:
    frame = make_ohlc(200, seed=7)
    summary = summarize_returns(frame["close"], method="log")
    assert summary.return_count == 199
    assert summary.descriptive.mean is not None
    assert len(summary.autocorr) >= 1


def test_assert_min_forward_lag() -> None:
    assert assert_min_forward_lag(1) == 1
    with pytest.raises(CausalityError):
        assert_min_forward_lag(0)


def test_forward_returns_alignment() -> None:
    close = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0])
    fwd = forward_returns(close, lag=1, horizon=1, method="simple")
    # At t=0: uses prices 101 → 102
    assert fwd.iloc[0] == pytest.approx(102.0 / 101.0 - 1.0)
    # Last lag+horizon bars NaN
    assert np.isnan(fwd.iloc[-1])
    assert np.isnan(fwd.iloc[-2])


def test_forward_returns_ignores_signal_bar() -> None:
    close = pd.Series(np.linspace(100.0, 110.0, 40))
    check = check_forward_return_ignores_signal_bar(close, lag=1, horizon=1)
    assert check.status is CausalityStatus.PASS
