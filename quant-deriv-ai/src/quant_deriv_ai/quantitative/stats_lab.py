"""Stats lab — causal descriptive / return statistics (LOT-005).

Pure NumPy/Pandas implementations; no look-ahead in rolling windows.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from quant_deriv_ai.core.exceptions import QuantDerivError
from quant_deriv_ai.quantitative.models import AutocorrPoint, DescriptiveStats, ReturnStats

FloatArray = NDArray[np.floating[Any]]


class StatsLabError(QuantDerivError):
    """Raised for invalid stats-lab inputs."""


def compute_returns(
    close: pd.Series | FloatArray | Sequence[float],
    *,
    method: str = "log",
) -> pd.Series:
    """Causal simple or log returns (first bar is NaN)."""
    series = pd.Series(np.asarray(close, dtype=float), dtype=float)
    method_key = method.strip().lower()
    if method_key == "log":
        # log(p_t / p_{t-1}) — uses only past and current price
        out = np.log(series / series.shift(1))
    elif method_key == "simple":
        out = series.pct_change()
    else:
        raise StatsLabError(f"unsupported return method: {method!r}")
    out.name = f"return_{method_key}"
    return out


def describe_series(
    values: pd.Series | FloatArray | Sequence[float],
    *,
    name: str = "series",
) -> DescriptiveStats:
    """Finite-sample descriptive statistics (NaNs excluded from moments)."""
    arr = np.asarray(values, dtype=float).ravel()
    missing = int(np.isnan(arr).sum())
    finite = arr[np.isfinite(arr)]
    count = int(finite.size)
    if count == 0:
        return DescriptiveStats(name=name, count=0, missing=missing)

    mean = float(np.mean(finite))
    std = float(np.std(finite, ddof=1)) if count > 1 else 0.0
    percentiles = np.percentile(finite, [5, 25, 50, 75, 95])
    skew = _skew(finite)
    kurt = _excess_kurtosis(finite)
    return DescriptiveStats(
        name=name,
        count=count,
        mean=mean,
        std=std,
        min=float(np.min(finite)),
        max=float(np.max(finite)),
        median=float(percentiles[2]),
        p05=float(percentiles[0]),
        p25=float(percentiles[1]),
        p75=float(percentiles[3]),
        p95=float(percentiles[4]),
        skew=skew,
        kurtosis=kurt,
        missing=missing,
    )


def rolling_mean(series: pd.Series, window: int) -> pd.Series:
    """Causal rolling mean (min_periods=window → NaN warmup)."""
    _require_positive_window(window)
    return series.astype(float).rolling(window=window, min_periods=window).mean()


def rolling_std(series: pd.Series, window: int) -> pd.Series:
    """Causal rolling sample std."""
    _require_positive_window(window)
    return series.astype(float).rolling(window=window, min_periods=window).std(ddof=1)


def rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    """Causal z-score using rolling mean/std (ddof=1)."""
    mu = rolling_mean(series, window)
    sigma = rolling_std(series, window)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (series.astype(float) - mu) / sigma
    z = z.replace([np.inf, -np.inf], np.nan)
    z.name = f"z_{window}"
    return z


def autocorrelation(
    series: pd.Series | FloatArray,
    lags: Sequence[int] | int = (1, 2, 5, 10),
) -> list[AutocorrPoint]:
    """Pearson autocorrelation at positive lags (causal lag of self)."""
    lag_list = list(range(1, lags + 1)) if isinstance(lags, int) else [int(x) for x in lags]
    arr = np.asarray(series, dtype=float).ravel()
    finite_mask = np.isfinite(arr)
    out: list[AutocorrPoint] = []
    for lag in lag_list:
        if lag < 1:
            raise StatsLabError(f"autocorr lag must be >= 1, got {lag}")
        if len(arr) <= lag:
            out.append(AutocorrPoint(lag=lag, value=None))
            continue
        x = arr[lag:]
        y = arr[:-lag]
        mask = finite_mask[lag:] & finite_mask[:-lag]
        if int(mask.sum()) < 3:
            out.append(AutocorrPoint(lag=lag, value=None))
            continue
        xv = x[mask]
        yv = y[mask]
        if float(np.std(xv)) == 0.0 or float(np.std(yv)) == 0.0:
            out.append(AutocorrPoint(lag=lag, value=None))
            continue
        corr = float(np.corrcoef(xv, yv)[0, 1])
        out.append(AutocorrPoint(lag=lag, value=corr))
    return out


def correlation_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    """Pairwise Pearson correlation on numeric columns (pairwise complete)."""
    numeric = frame.select_dtypes(include=[np.number])
    if numeric.empty:
        raise StatsLabError("correlation_matrix requires at least one numeric column")
    return numeric.corr(method="pearson")


def summarize_returns(
    close: pd.Series | FloatArray | Sequence[float],
    *,
    method: str = "log",
    autocorr_lags: Sequence[int] = (1, 2, 5, 10),
    annualization_factor: float = 252.0,
) -> ReturnStats:
    """Build a :class:`ReturnStats` bundle from a close series."""
    if annualization_factor <= 0:
        raise StatsLabError("annualization_factor must be > 0")
    rets = compute_returns(close, method=method)
    desc = describe_series(rets, name=f"return_{method.strip().lower()}")
    ac = autocorrelation(rets, lags=autocorr_lags)
    finite = rets.to_numpy(dtype=float)
    finite = finite[np.isfinite(finite)]
    hit: float | None = None
    ann_vol: float | None = None
    if finite.size > 0:
        hit = float(np.mean(finite > 0.0))
    if finite.size > 1 and desc.std is not None:
        ann_vol = float(desc.std * np.sqrt(annualization_factor))
    return ReturnStats(
        method=method.strip().lower(),
        bar_count=int(len(rets)),
        return_count=desc.count,
        descriptive=desc,
        autocorr=ac,
        hit_rate_positive=hit,
        annualized_vol=ann_vol,
        annualization_factor=float(annualization_factor),
    )


def _skew(arr: FloatArray) -> float | None:
    n = int(arr.size)
    if n < 3:
        return None
    m = float(np.mean(arr))
    s = float(np.std(arr, ddof=1))
    if s == 0.0:
        return 0.0
    m3 = float(np.mean((arr - m) ** 3))
    return m3 / (s**3)


def _excess_kurtosis(arr: FloatArray) -> float | None:
    n = int(arr.size)
    if n < 4:
        return None
    m = float(np.mean(arr))
    s = float(np.std(arr, ddof=1))
    if s == 0.0:
        return -3.0
    m4 = float(np.mean((arr - m) ** 4))
    return m4 / (s**4) - 3.0


def _require_positive_window(window: int) -> None:
    if window < 2:
        raise StatsLabError(f"rolling window must be >= 2, got {window}")
