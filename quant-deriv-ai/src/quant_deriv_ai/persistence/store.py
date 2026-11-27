"""Market-data store facade: Parquet + DuckDB + SQLite metadata + versioning."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from quant_deriv_ai.core.exceptions import PersistenceError
from quant_deriv_ai.core.logging import get_logger
from quant_deriv_ai.market_data.models import (
    DatasetManifest,
    DatasetStatus,
    ReconstructionMethod,
    SeriesKind,
    SeriesStats,
)
from quant_deriv_ai.market_data.normalize import merge_incremental, normalize_frame
from quant_deriv_ai.persistence.duckdb_store import DuckDbStore
from quant_deriv_ai.persistence.metadata import MetadataStore
from quant_deriv_ai.persistence.parquet_store import (
    content_hash_file,
    read_parquet,
    write_parquet,
)
from quant_deriv_ai.persistence.paths import DataPaths

log = get_logger(__name__)


class MarketDataStore:
    """Unified persistence for working series and immutable dataset versions."""

    def __init__(self, root: str | Path) -> None:
        self.paths = DataPaths(root)
        self.paths.ensure()
        self.metadata = MetadataStore(self.paths.metadata_db)
        self.duckdb = DuckDbStore(self.paths.duckdb_path)

    def read_working(
        self,
        *,
        symbol: str,
        kind: SeriesKind,
        timeframe: str | None = None,
    ) -> pd.DataFrame:
        path = self.paths.working_parquet(kind=kind, symbol=symbol, timeframe=timeframe)
        return read_parquet(path, kind=kind)

    def write_working(
        self,
        frame: pd.DataFrame,
        *,
        symbol: str,
        kind: SeriesKind,
        timeframe: str | None = None,
    ) -> SeriesStats:
        """Overwrite the mutable working series and refresh metadata + DuckDB view."""
        normalized = normalize_frame(frame, kind)
        path = self.paths.working_parquet(kind=kind, symbol=symbol, timeframe=timeframe)
        digest = write_parquet(normalized, path, kind=kind)
        first = last = None
        if not normalized.empty:
            times = pd.to_datetime(normalized["time"], utc=True)
            first = times.iloc[0].to_pydatetime()
            last = times.iloc[-1].to_pydatetime()
        self.metadata.upsert_series(
            symbol=symbol,
            kind=kind,
            timeframe=timeframe,
            row_count=len(normalized),
            first_time=first,
            last_time=last,
            content_hash=digest,
            parquet_path=str(path),
        )
        view = self.duckdb.view_name(kind=kind, symbol=symbol, timeframe=timeframe)
        self.duckdb.register_parquet(view_name=view, parquet_path=path)
        return SeriesStats(
            symbol=symbol,
            kind=kind,
            timeframe=timeframe,
            row_count=len(normalized),
            first_time=first,
            last_time=last,
            parquet_bytes=path.stat().st_size if path.is_file() else 0,
            content_hash=digest,
            status=DatasetStatus.MUTABLE,
        )

    def append_working(
        self,
        new_rows: pd.DataFrame,
        *,
        symbol: str,
        kind: SeriesKind,
        timeframe: str | None = None,
    ) -> SeriesStats:
        """Incremental update: merge + dedupe into the working series."""
        existing = self.read_working(symbol=symbol, kind=kind, timeframe=timeframe)
        merged = merge_incremental(existing, new_rows, kind)
        return self.write_working(merged, symbol=symbol, kind=kind, timeframe=timeframe)

    def pin_immutable(
        self,
        *,
        symbol: str,
        kind: SeriesKind,
        timeframe: str | None = None,
        version: str | None = None,
        notes: str = "",
        reconstruction_method: ReconstructionMethod = ReconstructionMethod.NONE,
        quality_ok: bool = True,
    ) -> DatasetManifest:
        """Copy working series into an immutable, reproducible versioned snapshot."""
        working = self.read_working(symbol=symbol, kind=kind, timeframe=timeframe)
        if working.empty:
            msg = f"cannot pin empty series {symbol}/{kind}/{timeframe}"
            raise PersistenceError(msg)

        dataset_id = _dataset_id(symbol=symbol, kind=kind, timeframe=timeframe)
        ver = version or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        dest_dir = self.paths.version_dir(dataset_id, ver)
        if dest_dir.exists():
            existing = self.metadata.get_version(dataset_id, ver)
            if existing is not None and existing.status is DatasetStatus.IMMUTABLE:
                # Idempotent if content matches
                current_hash = content_hash_file(
                    self.paths.working_parquet(kind=kind, symbol=symbol, timeframe=timeframe)
                )
                if existing.content_hash == current_hash:
                    return existing
                msg = f"immutable version already exists: {dataset_id}@{ver}"
                raise PersistenceError(msg)

        dest_parquet = self.paths.version_parquet(dataset_id, ver)
        digest = write_parquet(working, dest_parquet, kind=kind)
        times = pd.to_datetime(working["time"], utc=True)
        first = times.iloc[0].to_pydatetime()
        last = times.iloc[-1].to_pydatetime()
        manifest = DatasetManifest(
            dataset_id=dataset_id,
            version=ver,
            symbol=symbol,
            kind=kind,
            timeframe=timeframe,
            status=DatasetStatus.IMMUTABLE,
            created_at=datetime.now(UTC),
            content_hash=digest,
            row_count=len(working),
            first_time=first,
            last_time=last,
            source="mt5",
            reconstruction_method=reconstruction_method,
            notes=notes,
            quality_ok=quality_ok,
        )
        manifest_path = self.paths.version_manifest(dataset_id, ver)
        manifest_path.write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self.metadata.register_version(manifest, str(dest_parquet))
        log.info(
            "pinned immutable dataset {}@{} hash={} rows={}",
            dataset_id,
            ver,
            digest[:12],
            len(working),
        )
        return manifest

    def load_version(self, dataset_id: str, version: str) -> tuple[DatasetManifest, pd.DataFrame]:
        """Load an immutable dataset; refuse if metadata/file mismatch."""
        manifest = self.metadata.get_version(dataset_id, version)
        if manifest is None:
            msg = f"dataset version not found: {dataset_id}@{version}"
            raise PersistenceError(msg)
        path = self.paths.version_parquet(dataset_id, version)
        if not path.is_file():
            msg = f"immutable parquet missing for {dataset_id}@{version}"
            raise PersistenceError(msg)
        digest = content_hash_file(path)
        if digest != manifest.content_hash:
            msg = (
                f"integrity failure: {dataset_id}@{version} "
                f"expected hash {manifest.content_hash}, got {digest}"
            )
            raise PersistenceError(msg)
        frame = read_parquet(path, kind=manifest.kind)
        return manifest, frame

    def assert_immutable_untouched(self, dataset_id: str, version: str) -> DatasetManifest:
        """Integrity check: immutable snapshot bytes still match registered hash."""
        manifest, _ = self.load_version(dataset_id, version)
        return manifest

    def delete_working(
        self,
        *,
        symbol: str,
        kind: SeriesKind,
        timeframe: str | None = None,
    ) -> None:
        """Remove mutable working parquet only — never deletes immutable versions."""
        path = self.paths.working_parquet(kind=kind, symbol=symbol, timeframe=timeframe)
        if path.is_file():
            path.unlink()
        # Leave metadata row; caller may rewrite.

    def list_stats(self, symbol: str | None = None) -> list[SeriesStats]:
        rows = self.metadata.list_series(symbol=symbol)
        out: list[SeriesStats] = []
        for row in rows:
            path = Path(str(row["parquet_path"]))
            out.append(
                SeriesStats(
                    symbol=str(row["symbol"]),
                    kind=SeriesKind(str(row["kind"])),
                    timeframe=row.get("timeframe"),
                    row_count=int(row["row_count"]),
                    first_time=_parse(row.get("first_time")),
                    last_time=_parse(row.get("last_time")),
                    parquet_bytes=path.stat().st_size if path.is_file() else 0,
                    content_hash=row.get("content_hash"),
                    status=DatasetStatus.MUTABLE,
                )
            )
        return out

    def wipe_root_for_tests(self) -> None:
        """Dangerous helper for unit tests only."""
        if self.paths.root.exists():
            shutil.rmtree(self.paths.root)
        self.paths.ensure()
        self.metadata = MetadataStore(self.paths.metadata_db)
        self.duckdb = DuckDbStore(self.paths.duckdb_path)


def _dataset_id(*, symbol: str, kind: SeriesKind, timeframe: str | None) -> str:
    if kind is SeriesKind.CANDLES:
        return f"{symbol}_{kind.value}_{timeframe or 'NA'}"
    return f"{symbol}_{kind.value}"


def _parse(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.fromisoformat(str(value))
