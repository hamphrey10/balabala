"""Integrity + versioning tests: immutable datasets, hashes, incremental merge."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from quant_deriv_ai.core.exceptions import PersistenceError
from quant_deriv_ai.market_data.models import DatasetStatus, SeriesKind
from quant_deriv_ai.market_data.normalize import normalize_frame
from quant_deriv_ai.persistence.parquet_store import content_hash_file
from quant_deriv_ai.persistence.store import MarketDataStore


def _frame(n: int = 5, start: datetime | None = None) -> pd.DataFrame:
    start = start or datetime(2024, 6, 1, 0, 0, tzinfo=UTC)
    rows = []
    for i in range(n):
        t = start + timedelta(minutes=i)
        c = 1.1 + i * 0.001
        rows.append(
            {
                "symbol": "XAUUSD",
                "timeframe": "M1",
                "time": t,
                "open": c,
                "high": c + 0.01,
                "low": c - 0.01,
                "close": c,
                "tick_volume": 5,
                "spread": 2,
                "real_volume": 0,
                "is_reconstructed": False,
                "reconstruction_method": "none",
            }
        )
    return normalize_frame(pd.DataFrame(rows), SeriesKind.CANDLES)


def test_working_write_read_roundtrip(tmp_path: Path) -> None:
    store = MarketDataStore(tmp_path / "data")
    frame = _frame()
    stats = store.write_working(
        frame, symbol="XAUUSD", kind=SeriesKind.CANDLES, timeframe="M1"
    )
    assert stats.row_count == 5
    loaded = store.read_working(symbol="XAUUSD", kind=SeriesKind.CANDLES, timeframe="M1")
    assert len(loaded) == 5
    assert str(loaded["time"].dtype) == "datetime64[ns, UTC]"


def test_incremental_dedupe(tmp_path: Path) -> None:
    store = MarketDataStore(tmp_path / "data")
    base = _frame(5)
    store.write_working(base, symbol="XAUUSD", kind=SeriesKind.CANDLES, timeframe="M1")
    # Overlap last 2 bars + 3 new
    start = datetime(2024, 6, 1, 0, 3, tzinfo=UTC)
    more = _frame(5, start=start)
    stats = store.append_working(
        more, symbol="XAUUSD", kind=SeriesKind.CANDLES, timeframe="M1"
    )
    assert stats.row_count == 8  # 5 + 3 new


def test_immutable_pin_and_integrity(tmp_path: Path) -> None:
    store = MarketDataStore(tmp_path / "data")
    store.write_working(
        _frame(), symbol="XAUUSD", kind=SeriesKind.CANDLES, timeframe="M1"
    )
    manifest = store.pin_immutable(
        symbol="XAUUSD", kind=SeriesKind.CANDLES, timeframe="M1", version="v1"
    )
    assert manifest.status is DatasetStatus.IMMUTABLE
    assert manifest.content_hash
    loaded_m, loaded_df = store.load_version(manifest.dataset_id, "v1")
    assert loaded_m.content_hash == manifest.content_hash
    assert len(loaded_df) == 5
    # Tamper with immutable parquet → integrity failure
    path = store.paths.version_parquet(manifest.dataset_id, "v1")
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(PersistenceError, match="integrity"):
        store.load_version(manifest.dataset_id, "v1")


def test_immutable_reject_hash_change_reregister(tmp_path: Path) -> None:
    store = MarketDataStore(tmp_path / "data")
    store.write_working(
        _frame(), symbol="XAUUSD", kind=SeriesKind.CANDLES, timeframe="M1"
    )
    m1 = store.pin_immutable(
        symbol="XAUUSD", kind=SeriesKind.CANDLES, timeframe="M1", version="v1"
    )
    # Same content → idempotent
    m2 = store.pin_immutable(
        symbol="XAUUSD", kind=SeriesKind.CANDLES, timeframe="M1", version="v1"
    )
    assert m1.content_hash == m2.content_hash
    # Different working content with same version id → refuse overwrite
    store.write_working(
        _frame(6), symbol="XAUUSD", kind=SeriesKind.CANDLES, timeframe="M1"
    )
    with pytest.raises(PersistenceError):
        store.pin_immutable(
            symbol="XAUUSD", kind=SeriesKind.CANDLES, timeframe="M1", version="v1"
        )


def test_duckdb_view_query(tmp_path: Path) -> None:
    store = MarketDataStore(tmp_path / "data")
    store.write_working(
        _frame(), symbol="XAUUSD", kind=SeriesKind.CANDLES, timeframe="M1"
    )
    view = store.duckdb.view_name(
        kind=SeriesKind.CANDLES, symbol="XAUUSD", timeframe="M1"
    )
    stats = store.duckdb.stats_for_view(view)
    assert stats["row_count"] == 5


def test_content_hash_stable(tmp_path: Path) -> None:
    store = MarketDataStore(tmp_path / "data")
    frame = _frame()
    store.write_working(frame, symbol="XAUUSD", kind=SeriesKind.CANDLES, timeframe="M1")
    path = store.paths.working_parquet(
        kind=SeriesKind.CANDLES, symbol="XAUUSD", timeframe="M1"
    )
    h1 = content_hash_file(path)
    store.write_working(frame, symbol="XAUUSD", kind=SeriesKind.CANDLES, timeframe="M1")
    h2 = content_hash_file(path)
    assert h1 == h2
