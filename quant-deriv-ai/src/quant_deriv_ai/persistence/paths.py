"""Filesystem layout for market-data storage."""

from __future__ import annotations

from pathlib import Path

from quant_deriv_ai.market_data.models import SeriesKind


class DataPaths:
    """Resolves Parquet / DuckDB / SQLite paths under a data root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def ensure(self) -> None:
        for path in (
            self.root,
            self.parquet_root,
            self.versions_root,
            self.duckdb_root,
        ):
            path.mkdir(parents=True, exist_ok=True)

    @property
    def metadata_db(self) -> Path:
        return self.root / "metadata.sqlite"

    @property
    def parquet_root(self) -> Path:
        return self.root / "parquet"

    @property
    def versions_root(self) -> Path:
        return self.root / "versions"

    @property
    def duckdb_root(self) -> Path:
        return self.root / "duckdb"

    @property
    def duckdb_path(self) -> Path:
        return self.duckdb_root / "market.duckdb"

    def working_parquet(
        self,
        *,
        kind: SeriesKind,
        symbol: str,
        timeframe: str | None = None,
    ) -> Path:
        safe_symbol = _safe_name(symbol)
        if kind is SeriesKind.CANDLES:
            if not timeframe:
                msg = "timeframe required for candle parquet path"
                raise ValueError(msg)
            return self.parquet_root / "candles" / safe_symbol / timeframe.upper() / "data.parquet"
        return self.parquet_root / "ticks" / safe_symbol / "data.parquet"

    def version_dir(self, dataset_id: str, version: str) -> Path:
        return self.versions_root / _safe_name(dataset_id) / _safe_name(version)

    def version_parquet(self, dataset_id: str, version: str) -> Path:
        return self.version_dir(dataset_id, version) / "data.parquet"

    def version_manifest(self, dataset_id: str, version: str) -> Path:
        return self.version_dir(dataset_id, version) / "manifest.json"


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value)
