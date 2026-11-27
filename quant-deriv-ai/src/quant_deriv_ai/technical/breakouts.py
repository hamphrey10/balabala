"""Donchian / channel breakout detection (causal)."""

from __future__ import annotations

import pandas as pd

from quant_deriv_ai.indicators.core import donchian
from quant_deriv_ai.technical.models import BreakoutEvent, BreakoutSide


def detect_breakout(
    frame: pd.DataFrame,
    *,
    lookback: int = 20,
    confirm_close: bool = True,
) -> BreakoutEvent:
    """Detect breakout of prior Donchian channel.

    Uses channel computed on bars *before* the current bar for the level
    comparison (shift 1) so the current close is not inside the channel window
    that defines the breakout level — avoids look-ahead contamination.
    """
    if len(frame) < lookback + 1:
        close = float(frame["close"].iloc[-1]) if len(frame) else 0.0
        return BreakoutEvent(side=BreakoutSide.NONE, level=0.0, close=close, lookback=lookback)

    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    close_s = frame["close"].astype(float)
    channel = donchian(high, low, lookback)
    # Prior channel (exclude current bar from level definition).
    prior_upper = channel["donchian_upper"].shift(1)
    prior_lower = channel["donchian_lower"].shift(1)

    last_close = float(close_s.iloc[-1])
    upper = prior_upper.iloc[-1]
    lower = prior_lower.iloc[-1]
    if pd.isna(upper) or pd.isna(lower):
        return BreakoutEvent(
            side=BreakoutSide.NONE,
            level=0.0,
            close=last_close,
            lookback=lookback,
        )

    side = BreakoutSide.NONE
    level = float(upper)
    if last_close > float(upper):
        side = BreakoutSide.UP
        level = float(upper)
    elif last_close < float(lower):
        side = BreakoutSide.DOWN
        level = float(lower)

    confirmed = side is not BreakoutSide.NONE
    if confirm_close and side is BreakoutSide.UP:
        confirmed = last_close > float(upper)
    elif confirm_close and side is BreakoutSide.DOWN:
        confirmed = last_close < float(lower)

    return BreakoutEvent(
        side=side,
        level=level,
        close=last_close,
        confirmed=confirmed,
        lookback=lookback,
    )
