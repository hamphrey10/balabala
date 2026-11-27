"""Collect historical and continuous market series from the MT5 DEMO connector.

No orders. Instruments are discovered/selected dynamically via the client.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol

import pandas as pd

from quant_deriv_ai.core.logging import get_logger
from quant_deriv_ai.execution.mt5.models import Candle, TickData
from quant_deriv_ai.market_data.normalize import candles_to_frame, ticks_to_frame
from quant_deriv_ai.market_data.timeframes import assert_available_timeframe

log = get_logger(__name__)

# MT5 Python docs: copy_ticks_* may return at most this many rows per call.
_TICK_PAGE_SIZE = 100_000


class MarketDataSource(Protocol):
    """Minimal read-only source protocol (satisfied by ``Mt5Client``)."""

    def symbol_select(self, symbol: str, enable: bool = True) -> bool: ...

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: str | int,
        date_from: datetime,
        date_to: datetime,
    ) -> list[Candle]: ...

    def copy_ticks_from(
        self,
        symbol: str,
        date_from: datetime,
        count: int,
        *,
        flags: int | None = None,
    ) -> list[TickData]: ...

    def copy_ticks_range(
        self,
        symbol: str,
        date_from: datetime,
        date_to: datetime,
        *,
        flags: int | None = None,
    ) -> list[TickData]: ...


class MarketDataCollector:
    """Fetches candles/ticks and returns normalized UTC DataFrames."""

    def __init__(self, source: MarketDataSource) -> None:
        self._source = source

    def download_candles(
        self,
        symbol: str,
        timeframe: str,
        date_from: datetime,
        date_to: datetime | None = None,
    ) -> pd.DataFrame:
        tf = assert_available_timeframe(timeframe)
        end = date_to or datetime.now(UTC)
        self._source.symbol_select(symbol, True)
        candles = self._source.copy_rates_range(symbol, tf, date_from, end)
        log.info(
            "collected candles symbol={} tf={} rows={} from={} to={}",
            symbol,
            tf,
            len(candles),
            date_from.isoformat(),
            end.isoformat(),
        )
        return candles_to_frame(candles)

    def download_ticks(
        self,
        symbol: str,
        date_from: datetime,
        date_to: datetime | None = None,
        *,
        count: int | None = None,
    ) -> pd.DataFrame:
        end = _as_utc(date_to or datetime.now(UTC))
        start = _as_utc(date_from)
        self._source.symbol_select(symbol, True)
        if count is not None:
            ticks = self._source.copy_ticks_from(symbol, start, count)
            frame = ticks_to_frame(ticks)
            if not frame.empty:
                end_ts = pd.Timestamp(end)
                frame = frame.loc[frame["time"] <= end_ts].reset_index(drop=True)
        else:
            frame = self._download_ticks_range_paginated(symbol, start, end)
        log.info(
            "collected ticks symbol={} rows={} from={} to={}",
            symbol,
            len(frame),
            start.isoformat(),
            end.isoformat(),
        )
        return frame

    def continuous_ticks(
        self,
        symbol: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        lookback: timedelta = timedelta(minutes=5),
    ) -> pd.DataFrame:
        """Fetch ticks from ``since`` through ``until`` (default: now), paginated.

        Does **not** cap at a fixed count — callers that need a bounded sample
        should use ``download_ticks(..., count=...)`` explicitly.
        """
        start = _as_utc(since or (datetime.now(UTC) - lookback))
        end = _as_utc(until or datetime.now(UTC))
        return self.download_ticks(symbol, start, end)

    def _download_ticks_range_paginated(
        self,
        symbol: str,
        date_from: datetime,
        date_to: datetime,
    ) -> pd.DataFrame:
        """Fetch the full [from, to] tick window, paging when MT5 truncates."""
        chunks: list[pd.DataFrame] = []
        cursor = date_from
        end = date_to
        end_ts = pd.Timestamp(end)
        pages = 0
        use_range = hasattr(self._source, "copy_ticks_range")
        # Allow from == to (same-second windows with multiple ticks).
        while cursor <= end:
            pages += 1
            if use_range:
                batch = self._source.copy_ticks_range(symbol, cursor, end)
            else:
                batch = self._source.copy_ticks_from(symbol, cursor, _TICK_PAGE_SIZE)
            if not batch:
                break
            frame = ticks_to_frame(batch)
            if frame.empty:
                break
            frame = frame.loc[frame["time"] <= end_ts].reset_index(drop=True)
            if frame.empty:
                break
            chunks.append(frame)
            last_time = pd.to_datetime(frame["time"], utc=True).iloc[-1].to_pydatetime()
            # Advance past the last observed second (MT5 tick time is second-res).
            next_cursor = last_time + timedelta(seconds=1)
            if next_cursor <= cursor:
                break
            cursor = next_cursor
            # Short page ⇒ terminal returned everything available for this window.
            if len(batch) < _TICK_PAGE_SIZE:
                break
            if pages > 10_000:
                log.warning("tick pagination safety stop pages={}", pages)
                break
        if not chunks:
            return ticks_to_frame([])
        return pd.concat(chunks, ignore_index=True)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
