"""Session-aware gap helpers — weekends / market closures are not 'missing' bars."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

from quant_deriv_ai.market_data.timeframes import assert_available_timeframe, timeframe_delta


def max_intra_session_gap(timeframe: str) -> timedelta:
    """Largest gap still treated as an intra-session hole (not a market closure).

    Gaps larger than this (weekends, holidays, daily break) are session breaks and
    must not be reported as missing or fabricated by reconstruction.
    """
    tf = assert_available_timeframe(timeframe)
    delta = timeframe_delta(tf)
    # Gaps *larger than* this value are session breaks (weekends / holidays).
    # D1: only a single missing weekday (gap == 2 days) is intra-session.
    # Friday→Monday = 3 days and long weekends (≥4 days) must be closures.
    if tf == "D1":
        return timedelta(days=2)
    # Intraday: 6 bars or 2 hours, whichever is larger.
    return max(delta * 6, timedelta(hours=2))


def intra_session_missing_times(
    times: pd.Series | pd.DatetimeIndex,
    *,
    timeframe: str,
) -> pd.DatetimeIndex:
    """Return expected bar times that are missing *within* sessions only.

    Builds candidate slots only between consecutive observations whose gap is at
    most ``max_intra_session_gap`` — never across weekends/closures.
    """
    tf = assert_available_timeframe(timeframe)
    delta = timeframe_delta(tf)
    max_gap = max_intra_session_gap(tf)
    idx = pd.DatetimeIndex(pd.to_datetime(times, utc=True)).drop_duplicates().sort_values()
    if len(idx) < 2:
        return pd.DatetimeIndex([], tz="UTC")

    missing: list[pd.Timestamp] = []
    for left, right in zip(idx[:-1], idx[1:], strict=True):
        gap = right - left
        if gap <= delta:
            continue
        if gap > max_gap:
            # Session break (weekend / holiday / market closed) — not missing data.
            continue
        # Fill expected slots strictly between left and right.
        cursor = left + pd.Timedelta(delta)
        while cursor < right:
            missing.append(cursor)
            cursor = cursor + pd.Timedelta(delta)
    if not missing:
        return pd.DatetimeIndex([], tz="UTC")
    return pd.DatetimeIndex(missing, tz="UTC")
