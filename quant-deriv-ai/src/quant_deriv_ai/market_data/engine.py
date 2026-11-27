"""Market Data Engine — collect, validate, normalize, store, version."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from quant_deriv_ai.config.settings import DataSettings
from quant_deriv_ai.core.logging import get_logger
from quant_deriv_ai.market_data.collector import MarketDataCollector, MarketDataSource
from quant_deriv_ai.market_data.models import (
    DatasetManifest,
    DownloadResult,
    QualityReport,
    ReconstructionMethod,
    SeriesKind,
    SeriesStats,
    UpdateResult,
)
from quant_deriv_ai.market_data.normalize import dedupe_subset, normalize_frame
from quant_deriv_ai.market_data.quality import validate_series
from quant_deriv_ai.market_data.reconstruct import reconstruct_candles
from quant_deriv_ai.market_data.timeframes import AVAILABLE_TIMEFRAMES, assert_available_timeframe
from quant_deriv_ai.persistence.store import MarketDataStore

log = get_logger(__name__)


class MarketDataEngine:
    """Orchestrates multi-instrument / multi-timeframe market-data workflows."""

    def __init__(
        self,
        store: MarketDataStore,
        source: MarketDataSource | None = None,
        settings: DataSettings | None = None,
    ) -> None:
        self.store = store
        self.settings = settings or DataSettings()
        self.collector = MarketDataCollector(source) if source is not None else None

    @classmethod
    def from_root(
        cls,
        root: str | Path,
        source: MarketDataSource | None = None,
        settings: DataSettings | None = None,
    ) -> MarketDataEngine:
        return cls(MarketDataStore(root), source=source, settings=settings)

    def download_candles(
        self,
        symbol: str,
        timeframe: str,
        date_from: datetime,
        date_to: datetime | None = None,
        *,
        pin_version: str | None = None,
        reconstruct: ReconstructionMethod = ReconstructionMethod.NONE,
    ) -> DownloadResult:
        tf = assert_available_timeframe(timeframe)
        if self.collector is None:
            msg = "no market-data source configured (MT5 client required for download)"
            raise RuntimeError(msg)
        frame = self.collector.download_candles(symbol, tf, date_from, date_to)
        before = len(frame)
        frame = normalize_frame(frame, SeriesKind.CANDLES)
        if reconstruct is not ReconstructionMethod.NONE:
            frame = reconstruct_candles(
                frame,
                timeframe=tf,
                method=reconstruct,
                allow=self.settings.allow_reconstruction,
            )
        # Dedupe incoming batch, then merge into existing working series (never wipe).
        deduped = frame.drop_duplicates(subset=dedupe_subset(SeriesKind.CANDLES), keep="last")
        rows_deduped = before - len(deduped) if before >= len(deduped) else 0
        before_n = len(
            self.store.read_working(symbol=symbol, kind=SeriesKind.CANDLES, timeframe=tf)
        )
        stats = self.store.append_working(
            deduped, symbol=symbol, kind=SeriesKind.CANDLES, timeframe=tf
        )
        quality = self.validate(
            symbol, SeriesKind.CANDLES, timeframe=tf, require_fresh=False
        )
        version = None
        if pin_version is not None:
            # pin_version="" means auto version stamp
            manifest = self.store.pin_immutable(
                symbol=symbol,
                kind=SeriesKind.CANDLES,
                timeframe=tf,
                version=pin_version or None,
                reconstruction_method=reconstruct,
                quality_ok=quality.ok,
            )
            version = manifest.version
        return DownloadResult(
            symbol=symbol,
            kind=SeriesKind.CANDLES,
            timeframe=tf,
            rows_fetched=before,
            rows_written=max(0, stats.row_count - before_n),
            rows_deduped=max(0, rows_deduped),
            first_time=stats.first_time,
            last_time=stats.last_time,
            quality=quality,
            version=version,
        )

    def download_ticks(
        self,
        symbol: str,
        date_from: datetime,
        date_to: datetime | None = None,
        *,
        count: int | None = None,
        pin_version: str | None = None,
    ) -> DownloadResult:
        if self.collector is None:
            msg = "no market-data source configured (MT5 client required for download)"
            raise RuntimeError(msg)
        frame = self.collector.download_ticks(symbol, date_from, date_to, count=count)
        before = len(frame)
        frame = normalize_frame(frame, SeriesKind.TICKS)
        # Never collapse same-second ticks — dedupe on full quote identity.
        deduped = frame.drop_duplicates(subset=dedupe_subset(SeriesKind.TICKS), keep="last")
        before_n = len(self.store.read_working(symbol=symbol, kind=SeriesKind.TICKS))
        stats = self.store.append_working(deduped, symbol=symbol, kind=SeriesKind.TICKS)
        quality = self.validate(symbol, SeriesKind.TICKS, require_fresh=False)
        version = None
        if pin_version is not None:
            manifest = self.store.pin_immutable(
                symbol=symbol,
                kind=SeriesKind.TICKS,
                version=pin_version or None,
                quality_ok=quality.ok,
            )
            version = manifest.version
        return DownloadResult(
            symbol=symbol,
            kind=SeriesKind.TICKS,
            rows_fetched=before,
            rows_written=max(0, stats.row_count - before_n),
            rows_deduped=max(0, before - len(deduped)),
            first_time=stats.first_time,
            last_time=stats.last_time,
            quality=quality,
            version=version,
        )

    def download_multi(
        self,
        symbols: list[str],
        timeframes: list[str] | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        *,
        include_ticks: bool = False,
    ) -> list[DownloadResult]:
        """Download candles for multiple instruments/timeframes (and optional ticks)."""
        raw_tfs = timeframes or list(self.settings.default_timeframes)
        tfs = [assert_available_timeframe(t) for t in raw_tfs]
        start = date_from or (datetime.now(UTC) - timedelta(days=7))
        results: list[DownloadResult] = []
        for symbol in symbols:
            for tf in tfs:
                results.append(self.download_candles(symbol, tf, start, date_to))
            if include_ticks:
                results.append(self.download_ticks(symbol, start, date_to))
        return results

    def update_candles(self, symbol: str, timeframe: str) -> UpdateResult:
        """Incremental candle update from last stored timestamp."""
        tf = assert_available_timeframe(timeframe)
        if self.collector is None:
            msg = "no market-data source configured"
            raise RuntimeError(msg)
        existing = self.store.read_working(
            symbol=symbol, kind=SeriesKind.CANDLES, timeframe=tf
        )
        if existing.empty:
            # Fall back to a short historical window
            start = datetime.now(UTC) - timedelta(days=1)
        else:
            start = pd.to_datetime(existing["time"], utc=True).iloc[-1].to_pydatetime()
        frame = self.collector.download_candles(symbol, tf, start, datetime.now(UTC))
        before = self.store.read_working(
            symbol=symbol, kind=SeriesKind.CANDLES, timeframe=tf
        )
        before_n = len(before)
        stats = self.store.append_working(
            frame, symbol=symbol, kind=SeriesKind.CANDLES, timeframe=tf
        )
        quality = self.validate(
            symbol, SeriesKind.CANDLES, timeframe=tf, require_fresh=True
        )
        return UpdateResult(
            symbol=symbol,
            kind=SeriesKind.CANDLES,
            timeframe=tf,
            rows_added=max(0, stats.row_count - before_n),
            from_time=start,
            to_time=stats.last_time,
            quality=quality,
        )

    def update_ticks(self, symbol: str) -> UpdateResult:
        if self.collector is None:
            msg = "no market-data source configured"
            raise RuntimeError(msg)
        existing = self.store.read_working(symbol=symbol, kind=SeriesKind.TICKS)
        if existing.empty:
            since = datetime.now(UTC) - timedelta(minutes=5)
        else:
            since = pd.to_datetime(existing["time"], utc=True).iloc[-1].to_pydatetime()
        before_n = len(existing)
        until = datetime.now(UTC)
        # Full range to now (paginated) — never a fixed 5000-tick cap.
        frame = self.collector.continuous_ticks(symbol, since=since, until=until)
        stats = self.store.append_working(frame, symbol=symbol, kind=SeriesKind.TICKS)
        quality = self.validate(symbol, SeriesKind.TICKS, require_fresh=True)
        return UpdateResult(
            symbol=symbol,
            kind=SeriesKind.TICKS,
            rows_added=max(0, stats.row_count - before_n),
            from_time=since,
            to_time=stats.last_time,
            quality=quality,
        )

    def validate(
        self,
        symbol: str,
        kind: SeriesKind,
        timeframe: str | None = None,
        *,
        now: datetime | None = None,
        require_fresh: bool = False,
    ) -> QualityReport:
        frame = self.store.read_working(symbol=symbol, kind=kind, timeframe=timeframe)
        return validate_series(
            frame,
            symbol=symbol,
            kind=kind,
            timeframe=timeframe,
            now=now,
            freshness_max_age_s=self.settings.freshness_max_age_s,
            outlier_zscore=self.settings.outlier_zscore,
            require_fresh=require_fresh,
        )

    def inspect(
        self,
        symbol: str,
        kind: SeriesKind,
        timeframe: str | None = None,
        *,
        head: int = 5,
        tail: int = 5,
    ) -> dict[str, object]:
        frame = self.store.read_working(symbol=symbol, kind=kind, timeframe=timeframe)
        quality = self.validate(symbol, kind, timeframe=timeframe)
        meta = self.store.metadata.get_series(symbol=symbol, kind=kind, timeframe=timeframe)
        return {
            "symbol": symbol,
            "kind": kind.value,
            "timeframe": timeframe,
            "row_count": len(frame),
            "head": frame.head(head).to_dict(orient="records"),
            "tail": frame.tail(tail).to_dict(orient="records"),
            "quality": quality.model_dump(mode="json"),
            "metadata": meta,
        }

    def stats(self, symbol: str | None = None) -> list[SeriesStats]:
        return self.store.list_stats(symbol=symbol)

    def pin(
        self,
        symbol: str,
        kind: SeriesKind,
        timeframe: str | None = None,
        *,
        version: str | None = None,
        notes: str = "",
        require_fresh: bool = False,
    ) -> DatasetManifest:
        quality = self.validate(
            symbol, kind, timeframe=timeframe, require_fresh=require_fresh
        )
        return self.store.pin_immutable(
            symbol=symbol,
            kind=kind,
            timeframe=timeframe,
            version=version,
            notes=notes,
            quality_ok=quality.ok,
        )

    @property
    def available_timeframes(self) -> tuple[str, ...]:
        return AVAILABLE_TIMEFRAMES
