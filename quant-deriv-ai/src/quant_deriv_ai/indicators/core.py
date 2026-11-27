"""Vectorized technical indicators — causal (no look-ahead).

All rolling / ewm windows use only current and past observations.
Warm-up bars are NaN; values are never forward-filled from the future.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from quant_deriv_ai.indicators.base import (
    as_float_series,
    causal_ema,
    causal_rolling_mean,
    require_columns,
    require_positive_int,
)


def sma(close: pd.Series | NDArray[np.floating[Any]], period: int = 20) -> pd.Series:
    """Simple moving average."""
    period = require_positive_int("period", period)
    series = as_float_series(close, name="close")
    out = causal_rolling_mean(series, period)
    out.name = f"sma_{period}"
    return out


def ema(close: pd.Series | NDArray[np.floating[Any]], period: int = 20) -> pd.Series:
    """Exponential moving average (adjust=False)."""
    period = require_positive_int("period", period)
    series = as_float_series(close, name="close")
    out = causal_ema(series, period)
    out.name = f"ema_{period}"
    return out


def rsi(close: pd.Series | NDArray[np.floating[Any]], period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder / EMA of gains & losses)."""
    period = require_positive_int("period", period)
    series = as_float_series(close, name="close")
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    # When avg_loss == 0 and avg_gain > 0 → RSI = 100
    out = out.where(avg_loss != 0.0, 100.0)
    out = out.where(~(avg_loss.eq(0.0) & avg_gain.eq(0.0)), 50.0)
    out.name = f"rsi_{period}"
    return out


def macd(
    close: pd.Series | NDArray[np.floating[Any]],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """MACD line, signal line, and histogram."""
    fast = require_positive_int("fast", fast)
    slow = require_positive_int("slow", slow)
    signal = require_positive_int("signal", signal)
    if fast >= slow:
        from quant_deriv_ai.indicators.base import IndicatorError

        raise IndicatorError(f"macd fast ({fast}) must be < slow ({slow})")
    series = as_float_series(close, name="close")
    fast_ema = causal_ema(series, fast)
    slow_ema = causal_ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = causal_ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame(
        {
            "macd": macd_line,
            "macd_signal": signal_line,
            "macd_hist": hist,
        },
        index=series.index,
    )


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """True range (causal — uses prior close only)."""
    prev_close = close.shift(1)
    ranges = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(
    high: pd.Series | NDArray[np.floating[Any]],
    low: pd.Series | NDArray[np.floating[Any]],
    close: pd.Series | NDArray[np.floating[Any]],
    period: int = 14,
) -> pd.Series:
    """Average True Range (Wilder smoothing)."""
    period = require_positive_int("period", period)
    h = as_float_series(high, name="high")
    low_s = as_float_series(low, name="low")
    c = as_float_series(close, name="close")
    tr = true_range(h, low_s, c)
    out = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    out.name = f"atr_{period}"
    return out


def adx(
    high: pd.Series | NDArray[np.floating[Any]],
    low: pd.Series | NDArray[np.floating[Any]],
    close: pd.Series | NDArray[np.floating[Any]],
    period: int = 14,
) -> pd.DataFrame:
    """Average Directional Index with +DI / -DI (Wilder)."""
    period = require_positive_int("period", period)
    h = as_float_series(high, name="high")
    low_s = as_float_series(low, name="low")
    c = as_float_series(close, name="close")
    up = h.diff()
    down = -low_s.diff()
    plus_dm = pd.Series(
        np.where((up > down) & (up > 0), up, 0.0),
        index=h.index,
        dtype=float,
    )
    minus_dm = pd.Series(
        np.where((down > up) & (down > 0), down, 0.0),
        index=h.index,
        dtype=float,
    )
    tr = true_range(h, low_s, c)
    atr_s = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    plus_di = 100.0 * (
        plus_dm.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean() / atr_s
    )
    minus_di = 100.0 * (
        minus_dm.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean() / atr_s
    )
    di_sum = (plus_di + minus_di).replace(0.0, np.nan)
    dx = (100.0 * (plus_di - minus_di).abs() / di_sum).fillna(0.0)
    adx_s = dx.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    return pd.DataFrame(
        {"adx": adx_s, "plus_di": plus_di, "minus_di": minus_di},
        index=h.index,
    )


def bollinger(
    close: pd.Series | NDArray[np.floating[Any]],
    period: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """Bollinger Bands (mid = SMA, upper/lower = mid ± num_std * std)."""
    period = require_positive_int("period", period)
    if num_std <= 0:
        from quant_deriv_ai.indicators.base import IndicatorError

        raise IndicatorError(f"num_std must be > 0, got {num_std}")
    series = as_float_series(close, name="close")
    mid = causal_rolling_mean(series, period)
    std = series.rolling(window=period, min_periods=period).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    width = (upper - lower) / mid.replace(0.0, np.nan)
    return pd.DataFrame(
        {
            "bb_mid": mid,
            "bb_upper": upper,
            "bb_lower": lower,
            "bb_width": width,
        },
        index=series.index,
    )


def stochastic(
    high: pd.Series | NDArray[np.floating[Any]],
    low: pd.Series | NDArray[np.floating[Any]],
    close: pd.Series | NDArray[np.floating[Any]],
    k_period: int = 14,
    d_period: int = 3,
) -> pd.DataFrame:
    """Stochastic oscillator %K / %D."""
    k_period = require_positive_int("k_period", k_period)
    d_period = require_positive_int("d_period", d_period)
    h = as_float_series(high, name="high")
    low_s = as_float_series(low, name="low")
    c = as_float_series(close, name="close")
    lowest = low_s.rolling(window=k_period, min_periods=k_period).min()
    highest = h.rolling(window=k_period, min_periods=k_period).max()
    denom = (highest - lowest).replace(0.0, np.nan)
    k = 100.0 * (c - lowest) / denom
    d = k.rolling(window=d_period, min_periods=d_period).mean()
    return pd.DataFrame({"stoch_k": k, "stoch_d": d}, index=c.index)


def donchian(
    high: pd.Series | NDArray[np.floating[Any]],
    low: pd.Series | NDArray[np.floating[Any]],
    period: int = 20,
) -> pd.DataFrame:
    """Donchian channel (causal rolling max/min of high/low)."""
    period = require_positive_int("period", period)
    h = as_float_series(high, name="high")
    low_s = as_float_series(low, name="low")
    upper = h.rolling(window=period, min_periods=period).max()
    lower = low_s.rolling(window=period, min_periods=period).min()
    mid = (upper + lower) / 2.0
    return pd.DataFrame(
        {"donchian_upper": upper, "donchian_mid": mid, "donchian_lower": lower},
        index=h.index,
    )


def roc(close: pd.Series | NDArray[np.floating[Any]], period: int = 12) -> pd.Series:
    """Rate of Change (%)."""
    period = require_positive_int("period", period)
    series = as_float_series(close, name="close")
    prev = series.shift(period)
    out = 100.0 * (series - prev) / prev.replace(0.0, np.nan)
    out.name = f"roc_{period}"
    return out


def momentum(close: pd.Series | NDArray[np.floating[Any]], period: int = 10) -> pd.Series:
    """Momentum (close - close[n])."""
    period = require_positive_int("period", period)
    series = as_float_series(close, name="close")
    out = series - series.shift(period)
    out.name = f"mom_{period}"
    return out


def cci(
    high: pd.Series | NDArray[np.floating[Any]],
    low: pd.Series | NDArray[np.floating[Any]],
    close: pd.Series | NDArray[np.floating[Any]],
    period: int = 20,
) -> pd.Series:
    """Commodity Channel Index."""
    period = require_positive_int("period", period)
    h = as_float_series(high, name="high")
    low_s = as_float_series(low, name="low")
    c = as_float_series(close, name="close")
    tp = (h + low_s + c) / 3.0
    sma_tp = causal_rolling_mean(tp, period)
    mad = tp.rolling(window=period, min_periods=period).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))),
        raw=True,
    )
    out = (tp - sma_tp) / (0.015 * mad.replace(0.0, np.nan))
    out.name = f"cci_{period}"
    return out


def williams_r(
    high: pd.Series | NDArray[np.floating[Any]],
    low: pd.Series | NDArray[np.floating[Any]],
    close: pd.Series | NDArray[np.floating[Any]],
    period: int = 14,
) -> pd.Series:
    """Williams %R."""
    period = require_positive_int("period", period)
    h = as_float_series(high, name="high")
    low_s = as_float_series(low, name="low")
    c = as_float_series(close, name="close")
    highest = h.rolling(window=period, min_periods=period).max()
    lowest = low_s.rolling(window=period, min_periods=period).min()
    denom = (highest - lowest).replace(0.0, np.nan)
    out = -100.0 * (highest - c) / denom
    out.name = f"williams_r_{period}"
    return out


def historical_volatility(
    close: pd.Series | NDArray[np.floating[Any]],
    period: int = 20,
    *,
    annualize: bool = False,
    periods_per_year: int = 252,
) -> pd.Series:
    """Historical volatility from log returns (sample std, causal rolling)."""
    period = require_positive_int("period", period)
    periods_per_year = require_positive_int("periods_per_year", periods_per_year)
    series = as_float_series(close, name="close")
    log_ret = np.log(series / series.shift(1))
    vol = log_ret.rolling(window=period, min_periods=period).std(ddof=1)
    if annualize:
        vol = vol * np.sqrt(float(periods_per_year))
    vol.name = f"hist_vol_{period}"
    return vol


def _param_int(params: dict[str, Any], key: str, default: int) -> int:
    return int(params.get(key, default))


def _param_float(params: dict[str, Any], key: str, default: float) -> float:
    return float(params.get(key, default))


def compute_from_ohlc(
    frame: pd.DataFrame,
    name: str,
    *,
    params: dict[str, Any] | None = None,
) -> pd.Series | pd.DataFrame:
    """Dispatch helper used by the registry for OHLC-based indicators."""
    from quant_deriv_ai.indicators.registry import get_indicator

    spec = get_indicator(name)
    p: dict[str, Any] = dict(params or {})
    require_columns(frame, ("open", "high", "low", "close"))
    close = frame["close"]
    high = frame["high"]
    low = frame["low"]

    if name == "sma":
        return sma(close, _param_int(p, "period", 20))
    if name == "ema":
        return ema(close, _param_int(p, "period", 20))
    if name == "rsi":
        return rsi(close, _param_int(p, "period", 14))
    if name == "macd":
        return macd(
            close,
            fast=_param_int(p, "fast", 12),
            slow=_param_int(p, "slow", 26),
            signal=_param_int(p, "signal", 9),
        )
    if name == "atr":
        return atr(high, low, close, _param_int(p, "period", 14))
    if name == "adx":
        return adx(high, low, close, _param_int(p, "period", 14))
    if name == "bollinger":
        return bollinger(close, _param_int(p, "period", 20), _param_float(p, "num_std", 2.0))
    if name == "stochastic":
        return stochastic(
            high,
            low,
            close,
            k_period=_param_int(p, "k_period", 14),
            d_period=_param_int(p, "d_period", 3),
        )
    if name == "donchian":
        return donchian(high, low, _param_int(p, "period", 20))
    if name == "roc":
        return roc(close, _param_int(p, "period", 12))
    if name == "momentum":
        return momentum(close, _param_int(p, "period", 10))
    if name == "cci":
        return cci(high, low, close, _param_int(p, "period", 20))
    if name == "williams_r":
        return williams_r(high, low, close, _param_int(p, "period", 14))
    if name == "hist_vol":
        return historical_volatility(
            close,
            _param_int(p, "period", 20),
            annualize=bool(p.get("annualize", False)),
            periods_per_year=_param_int(p, "periods_per_year", 252),
        )
    from quant_deriv_ai.indicators.base import IndicatorError

    raise IndicatorError(f"unsupported indicator in compute_from_ohlc: {name} ({spec.name})")
