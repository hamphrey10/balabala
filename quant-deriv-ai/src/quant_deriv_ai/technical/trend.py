"""Trend classification from moving averages, ADX, and structure."""

from __future__ import annotations

import pandas as pd

from quant_deriv_ai.indicators.core import adx, sma
from quant_deriv_ai.technical.models import StructureBias, TrendDirection, TrendState
from quant_deriv_ai.technical.structure import detect_swings, structure_bias_from_swings


def classify_trend(
    frame: pd.DataFrame,
    *,
    fast: int = 20,
    slow: int = 50,
    adx_period: int = 14,
    adx_trend_threshold: float = 20.0,
    swing_left: int = 2,
    swing_right: int = 2,
) -> TrendState:
    """Classify trend without look-ahead (uses last fully available bar)."""
    close = frame["close"].astype(float)
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    fast_s = sma(close, fast)
    slow_s = sma(close, slow)
    adx_df = adx(high, low, close, adx_period)

    fast_v = _last_finite(fast_s)
    slow_v = _last_finite(slow_s)
    adx_v = _last_finite(adx_df["adx"])
    plus_di = _last_finite(adx_df["plus_di"])
    minus_di = _last_finite(adx_df["minus_di"])

    swings = detect_swings(high, low, left=swing_left, right=swing_right)
    bias = structure_bias_from_swings(swings)

    direction = TrendDirection.UNKNOWN
    strength = 0.0

    # Insufficient history for SMA → remain UNKNOWN (not a fake sideways).
    if fast_v is None or slow_v is None:
        return TrendState(
            direction=TrendDirection.UNKNOWN,
            strength=0.0,
            adx=adx_v,
            sma_fast=fast_v,
            sma_slow=slow_v,
            structure_bias=bias,
        )

    ma_up = fast_v > slow_v
    ma_down = fast_v < slow_v
    strong = adx_v is not None and adx_v >= adx_trend_threshold

    if ma_up and (plus_di is None or minus_di is None or plus_di >= minus_di):
        direction = TrendDirection.UP
    elif ma_down and (plus_di is None or minus_di is None or minus_di >= plus_di):
        direction = TrendDirection.DOWN
    elif ma_up or ma_down:
        direction = TrendDirection.UP if ma_up else TrendDirection.DOWN
    else:
        # Equal SMAs → range / sideways.
        direction = TrendDirection.SIDEWAYS

    if strong and direction in (TrendDirection.UP, TrendDirection.DOWN):
        strength = min(1.0, float(adx_v) / 50.0) if adx_v is not None else 0.5
    elif direction is TrendDirection.SIDEWAYS:
        strength = 0.2
    else:
        strength = 0.4

    # Soft disagreement with structure → dampen strength.
    disagree = (
        bias is StructureBias.BULLISH and direction is TrendDirection.DOWN
    ) or (bias is StructureBias.BEARISH and direction is TrendDirection.UP)
    if disagree:
        strength *= 0.5
        direction = TrendDirection.SIDEWAYS

    return TrendState(
        direction=direction,
        strength=float(max(0.0, min(1.0, strength))),
        adx=adx_v,
        sma_fast=fast_v,
        sma_slow=slow_v,
        structure_bias=bias,
    )


def _last_finite(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.iloc[-1])
