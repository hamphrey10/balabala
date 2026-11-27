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
        end = date_to or datetime.now(UTC)
        self._source.symbol_select(symbol, True)
        if count is not None:
            ticks = self._source.copy_ticks_from(symbol, date_from, count)
        elif hasattr(self._source, "copy_ticks_range"):
            ticks = self._source.copy_ticks_range(symbol, date_from, end)
        else:
            # Fallback: bounded from-start fetch when range API absent.
            ticks = self._source.copy_ticks_from(symbol, date_from, 100_000)
        # Filter to window when using from/count
        frame = ticks_to_frame(ticks)
        if not frame.empty and date_to is not None:
            end_ts = pd.Timestamp(end if end.tzinfo else end.replace(tzinfo=UTC))
            frame = frame.loc[frame["time"] <= end_ts].reset_index(drop=True)
        log.info(
            "collected ticks symbol={} rows={} from={}",
            symbol,
            len(frame),
            date_from.isoformat(),
        )
        return frame

    def continuous_ticks(
        self,
        symbol: str,
        *,
        since: datetime | None = None,
        lookback: timedelta = timedelta(minutes=5),
        count: int = 5_000,
    ) -> pd.DataFrame:
        """Fetch a short recent tick window for continuous / incremental updates."""
        start = since or (datetime.now(UTC) - lookback)
        return self.download_ticks(symbol, start, count=count)
