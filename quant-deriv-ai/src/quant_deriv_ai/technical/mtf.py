"""Multi-timeframe consensus — independent per-TF analysis, then aggregate."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from quant_deriv_ai.indicators.core import rsi
from quant_deriv_ai.technical.models import (
    MTFConsensus,
    MTFTimeframeView,
    StructureBias,
    TrendDirection,
)
from quant_deriv_ai.technical.trend import classify_trend


def analyze_mtf(
    frames: Mapping[str, pd.DataFrame],
    *,
    rsi_period: int = 14,
    sma_fast: int = 20,
    sma_slow: int = 50,
    swing_left: int = 2,
    swing_right: int = 2,
) -> MTFConsensus:
    """Build MTF consensus from a mapping of timeframe → OHLCV frame.

    Each timeframe is analyzed independently (no resampling look-ahead across TFs).
    Trend parameters mirror the primary engine settings.
    """
    views: list[MTFTimeframeView] = []
    for tf in sorted(frames.keys()):
        frame = frames[tf]
        if frame.empty or "close" not in frame.columns:
            views.append(
                MTFTimeframeView(
                    timeframe=tf,
                    trend=TrendDirection.UNKNOWN,
                    structure_bias=StructureBias.UNKNOWN,
                )
            )
            continue
        trend = classify_trend(
            frame,
            fast=sma_fast,
            slow=sma_slow,
            swing_left=swing_left,
            swing_right=swing_right,
        )
        close = frame["close"].astype(float)
        rsi_s = rsi(close, rsi_period)
        rsi_v = float(rsi_s.dropna().iloc[-1]) if not rsi_s.dropna().empty else None
        views.append(
            MTFTimeframeView(
                timeframe=tf,
                trend=trend.direction,
                structure_bias=trend.structure_bias,
                last_close=float(close.iloc[-1]),
                rsi=rsi_v,
            )
        )

    directions = [v.trend for v in views if v.trend is not TrendDirection.UNKNOWN]
    if not directions:
        return MTFConsensus(
            aligned=False,
            dominant_trend=TrendDirection.UNKNOWN,
            views=views,
            notes="no usable timeframe trends",
        )

    up = sum(1 for d in directions if d is TrendDirection.UP)
    down = sum(1 for d in directions if d is TrendDirection.DOWN)
    if up > down and up >= (len(directions) + 1) // 2:
        dominant = TrendDirection.UP
    elif down > up and down >= (len(directions) + 1) // 2:
        dominant = TrendDirection.DOWN
    else:
        dominant = TrendDirection.SIDEWAYS

    aligned = all(d is dominant for d in directions) and dominant in (
        TrendDirection.UP,
        TrendDirection.DOWN,
    )
    notes = "aligned" if aligned else "mixed / not fully aligned"
    return MTFConsensus(
        aligned=aligned,
        dominant_trend=dominant,
        views=views,
        notes=notes,
    )
