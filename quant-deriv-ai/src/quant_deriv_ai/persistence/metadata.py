"""SQLite metadata store for series registry and immutable dataset versions."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quant_deriv_ai.core.exceptions import PersistenceError
from quant_deriv_ai.market_data.models import (
    DatasetManifest,
    DatasetStatus,
    ReconstructionMethod,
    SeriesKind,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS series (
    symbol TEXT NOT NULL,
    kind TEXT NOT NULL,
    timeframe TEXT,
    row_count INTEGER NOT NULL DEFAULT 0,
    first_time TEXT,
    last_time TEXT,
    content_hash TEXT,
    parquet_path TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (symbol, kind, timeframe)
);

CREATE TABLE IF NOT EXISTS dataset_versions (
    dataset_id TEXT NOT NULL,
    version TEXT NOT NULL,
    symbol TEXT NOT NULL,
    kind TEXT NOT NULL,
    timeframe TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    first_time TEXT,
    last_time TEXT,
    source TEXT NOT NULL,
    reconstruction_method TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    quality_ok INTEGER NOT NULL DEFAULT 1,
    extra_json TEXT NOT NULL DEFAULT '{}',
    parquet_path TEXT NOT NULL,
    PRIMARY KEY (dataset_id, version)
);
"""


class MetadataStore:
    """Thin SQLite wrapper — no secrets, no order state."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def upsert_series(
        self,
        *,
        symbol: str,
        kind: SeriesKind,
        timeframe: str | None,
        row_count: int,
        first_time: datetime | None,
        last_time: datetime | None,
        content_hash: str,
        parquet_path: str,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        tf_key = timeframe or ""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO series (
                    symbol, kind, timeframe, row_count, first_time, last_time,
                    content_hash, parquet_path, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, kind, timeframe) DO UPDATE SET
                    row_count=excluded.row_count,
                    first_time=excluded.first_time,
                    last_time=excluded.last_time,
                    content_hash=excluded.content_hash,
                    parquet_path=excluded.parquet_path,
                    updated_at=excluded.updated_at
                """,
                (
                    symbol,
                    kind.value,
                    tf_key,
                    row_count,
                    _iso(first_time),
                    _iso(last_time),
                    content_hash,
                    parquet_path,
                    now,
                ),
            )

    def get_series(
        self,
        *,
        symbol: str,
        kind: SeriesKind,
        timeframe: str | None = None,
    ) -> dict[str, Any] | None:
        tf_key = timeframe or ""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM series
                WHERE symbol=? AND kind=? AND timeframe=?
                """,
                (symbol, kind.value, tf_key),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        # Present empty timeframe key as None to callers.
        if data.get("timeframe") == "":
            data["timeframe"] = None
        return data

    def list_series(self, symbol: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if symbol:
                rows = conn.execute(
                    "SELECT * FROM series WHERE symbol=? ORDER BY kind, timeframe",
                    (symbol,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM series ORDER BY symbol, kind, timeframe"
                ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            data = dict(r)
            if data.get("timeframe") == "":
                data["timeframe"] = None
            out.append(data)
        return out

    def register_version(self, manifest: DatasetManifest, parquet_path: str) -> None:
        if manifest.status is not DatasetStatus.IMMUTABLE:
            msg = "only IMMUTABLE datasets may be registered as versions"
            raise PersistenceError(msg)
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT content_hash, status FROM dataset_versions
                WHERE dataset_id=? AND version=?
                """,
                (manifest.dataset_id, manifest.version),
            ).fetchone()
            if existing is not None:
                if existing["status"] == DatasetStatus.IMMUTABLE.value:
                    if existing["content_hash"] != manifest.content_hash:
                        msg = (
                            f"immutable dataset {manifest.dataset_id}@{manifest.version} "
                            "already exists with a different content hash"
                        )
                        raise PersistenceError(msg)
                    return  # idempotent same hash
                msg = f"dataset version {manifest.dataset_id}@{manifest.version} is not immutable"
                raise PersistenceError(msg)
            conn.execute(
                """
                INSERT INTO dataset_versions (
                    dataset_id, version, symbol, kind, timeframe, status, created_at,
                    content_hash, row_count, first_time, last_time, source,
                    reconstruction_method, notes, quality_ok, extra_json, parquet_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest.dataset_id,
                    manifest.version,
                    manifest.symbol,
                    manifest.kind.value,
                    manifest.timeframe,
                    manifest.status.value,
                    manifest.created_at.astimezone(UTC).isoformat(),
                    manifest.content_hash,
                    manifest.row_count,
                    _iso(manifest.first_time),
                    _iso(manifest.last_time),
                    manifest.source,
                    manifest.reconstruction_method.value,
                    manifest.notes,
                    1 if manifest.quality_ok else 0,
                    json.dumps(manifest.extra, sort_keys=True),
                    parquet_path,
                ),
            )

    def get_version(self, dataset_id: str, version: str) -> DatasetManifest | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM dataset_versions WHERE dataset_id=? AND version=?",
                (dataset_id, version),
            ).fetchone()
        if row is None:
            return None
        return _manifest_from_row(dict(row))

    def list_versions(
        self,
        *,
        symbol: str | None = None,
        dataset_id: str | None = None,
    ) -> list[DatasetManifest]:
        query = "SELECT * FROM dataset_versions WHERE 1=1"
        params: list[Any] = []
        if symbol:
            query += " AND symbol=?"
            params.append(symbol)
        if dataset_id:
            query += " AND dataset_id=?"
            params.append(dataset_id)
        query += " ORDER BY created_at"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_manifest_from_row(dict(r)) for r in rows]


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _manifest_from_row(row: dict[str, Any]) -> DatasetManifest:
    extra_raw = row.get("extra_json") or "{}"
    extra = json.loads(extra_raw) if isinstance(extra_raw, str) else {}
    return DatasetManifest(
        dataset_id=str(row["dataset_id"]),
        version=str(row["version"]),
        symbol=str(row["symbol"]),
        kind=SeriesKind(str(row["kind"])),
        timeframe=row.get("timeframe"),
        status=DatasetStatus(str(row["status"])),
        created_at=_parse_dt(row["created_at"]) or datetime.now(UTC),
        content_hash=str(row["content_hash"]),
        row_count=int(row["row_count"]),
        first_time=_parse_dt(row.get("first_time")),
        last_time=_parse_dt(row.get("last_time")),
        source=str(row.get("source") or "mt5"),
        reconstruction_method=ReconstructionMethod(
            str(row.get("reconstruction_method") or "none")
        ),
        notes=str(row.get("notes") or ""),
        quality_ok=bool(row.get("quality_ok", 1)),
        extra=extra if isinstance(extra, dict) else {},
    )
