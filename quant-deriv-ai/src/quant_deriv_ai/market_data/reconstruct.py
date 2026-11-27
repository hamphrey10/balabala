"""Controlled series reconstruction — never silent fabrication.

By default the engine leaves gaps. When reconstruction is explicitly enabled,
inserted rows are flagged with ``is_reconstructed=True`` and a method label so
backtests can exclude or audit them.

Only **intra-session** holes are filled — weekends / market closures are never
fabricated (see ``sessions.intra_session_missing_times``).
"""

from __future__ import annotations

import pandas as pd

from quant_deriv_ai.core.exceptions import QuantDerivError
from quant_deriv_ai.market_data.models import ReconstructionMethod, SeriesKind
from quant_deriv_ai.market_data.normalize import normalize_frame
from quant_deriv_ai.market_data.sessions import intra_session_missing_times
from quant_deriv_ai.market_data.timeframes import assert_available_timeframe


class ReconstructionForbiddenError(QuantDerivError):
    """Raised when reconstruction is requested but not allowed by policy/config."""


def reconstruct_candles(
    frame: pd.DataFrame,
    *,
    timeframe: str,
    method: ReconstructionMethod,
    allow: bool,
) -> pd.DataFrame:
    """Fill missing candle slots only when explicitly allowed and identified.

    ``NONE`` / ``MARK_GAP`` leave the series unchanged (gaps remain missing).
    ``FORWARD_FILL`` inserts bars carrying the previous close into OHLC and
    marks every inserted row as reconstructed. Closed-market intervals are
    never filled.
    """
    if method in {ReconstructionMethod.NONE, ReconstructionMethod.MARK_GAP}:
        return normalize_frame(frame, SeriesKind.CANDLES)

    if not allow:
        msg = (
            "reconstruction requested but allow_reconstruction=false — "
            "refusing to fabricate missing bars"
        )
        raise ReconstructionForbiddenError(msg)

    if method is not ReconstructionMethod.FORWARD_FILL:
        msg = f"unsupported reconstruction method: {method!r}"
        raise ReconstructionForbiddenError(msg)

    if frame.empty:
        return normalize_frame(frame, SeriesKind.CANDLES)

    tf = assert_available_timeframe(timeframe)
    base = normalize_frame(frame, SeriesKind.CANDLES)
    times = pd.to_datetime(base["time"], utc=True)
    missing = list(intra_session_missing_times(times, timeframe=tf))
    if not missing:
        return base

    # Forward-fill from last known close; never invent a synthetic price path beyond that.
    indexed = base.set_index("time").sort_index()
    rows: list[dict[str, object]] = []
    symbol = str(base["symbol"].iloc[0])
    for ts in missing:
        prior = indexed.loc[:ts]
        if prior.empty:
            continue
        last = prior.iloc[-1]
        close = float(last["close"])
        rows.append(
            {
                "symbol": symbol,
                "timeframe": tf,
                "time": pd.Timestamp(ts).to_pydatetime(),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "tick_volume": 0,
                "spread": int(last.get("spread", 0) or 0),
                "real_volume": 0,
                "is_reconstructed": True,
                "reconstruction_method": ReconstructionMethod.FORWARD_FILL.value,
            }
        )
    if not rows:
        return base
    filled = pd.concat([base, pd.DataFrame(rows)], ignore_index=True)
    return normalize_frame(filled, SeriesKind.CANDLES)
