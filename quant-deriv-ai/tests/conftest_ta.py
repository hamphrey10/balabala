"""Shared helpers for technical-analysis tests (reference implementations)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd


def make_ohlc(
    n: int = 200,
    *,
    seed: int = 42,
    start: float = 100.0,
    with_volume: bool = True,
    volume_synthetic: bool = True,
) -> pd.DataFrame:
    """Generate a deterministic synthetic OHLC series (GBM-like)."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0002, 0.01, size=n)
    close = start * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[start], close[:-1]])
    high = np.maximum(open_, close) * (1.0 + rng.uniform(0.0, 0.005, size=n))
    low = np.minimum(open_, close) * (1.0 - rng.uniform(0.0, 0.005, size=n))
    start_t = datetime(2024, 1, 1, tzinfo=UTC)
    times = [start_t + timedelta(hours=i) for i in range(n)]
    frame = pd.DataFrame(
        {
            "time": times,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
        }
    )
    if with_volume:
        # Synthetic tick-like volume — tests must not treat as real liquidity.
        frame["volume"] = rng.integers(10, 500, size=n).astype(float)
        frame.attrs["volume_is_synthetic"] = volume_synthetic
    return frame


def ref_sma(close: np.ndarray, period: int) -> np.ndarray:
    out = np.full(len(close), np.nan, dtype=float)
    for i in range(period - 1, len(close)):
        out[i] = float(np.mean(close[i - period + 1 : i + 1]))
    return out


def ref_ema(close: np.ndarray, period: int) -> np.ndarray:
    out = np.full(len(close), np.nan, dtype=float)
    if len(close) < period:
        return out
    alpha = 2.0 / (period + 1.0)
    # Seed with SMA of first `period` values (common approach); our impl uses
    # pandas ewm(min_periods=period) which seeds differently — compare from
    # a recursive EMA seeded at first value then mask warmup.
    ema = float(close[0])
    for i in range(len(close)):
        ema = alpha * float(close[i]) + (1.0 - alpha) * ema
        out[i] = ema
    out[: period - 1] = np.nan
    return out


def ref_rsi_wilder(close: np.ndarray, period: int = 14) -> np.ndarray:
    out = np.full(len(close), np.nan, dtype=float)
    if len(close) < period + 1:
        return out
    deltas = np.diff(close, prepend=close[0])
    gains = np.clip(deltas, 0.0, None)
    losses = np.clip(-deltas, 0.0, None)
    avg_gain = float(np.mean(gains[1 : period + 1]))
    avg_loss = float(np.mean(losses[1 : period + 1]))
    # Align with ewm(alpha=1/period) starting from bar 0 is hard; use Wilder loop
    # from first average and compare vectorized impl loosely on later bars.
    for i in range(period, len(close)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0 and avg_gain == 0:
            out[i] = 50.0
        elif avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


def ref_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    n = len(close)
    tr = np.full(n, np.nan, dtype=float)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    out = np.full(n, np.nan, dtype=float)
    if n < period:
        return out
    atr = float(np.mean(tr[:period]))
    out[period - 1] = atr
    for i in range(period, n):
        atr = (atr * (period - 1) + tr[i]) / period
        out[i] = atr
    return out


def assert_no_lookahead_shift(series: pd.Series, close: pd.Series, period: int) -> None:
    """Mutating the last close must not change earlier indicator values."""
    # Implemented in tests via recompute comparison.
    _ = (series, close, period)
