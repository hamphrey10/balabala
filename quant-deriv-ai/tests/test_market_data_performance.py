"""Lightweight performance checks for normalize / parquet / quality (mocked data)."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from quant_deriv_ai.market_data.models import SeriesKind
from quant_deriv_ai.market_data.normalize import normalize_frame
from quant_deriv_ai.market_data.quality import validate_series
from quant_deriv_ai.persistence.store import MarketDataStore


def _large_candles(n: int = 5_000) -> pd.DataFrame:
    start = datetime(2023, 1, 1, tzinfo=UTC)
    rows = {
        "symbol": ["Volatility 75 Index"] * n,
        "timeframe": ["M1"] * n,
        "time": [start + timedelta(minutes=i) for i in range(n)],
        "open": [100.0 + i * 0.01 for i in range(n)],
        "high": [100.1 + i * 0.01 for i in range(n)],
        "low": [99.9 + i * 0.01 for i in range(n)],
        "close": [100.0 + i * 0.01 for i in range(n)],
        "tick_volume": [10] * n,
        "spread": [1] * n,
        "real_volume": [0] * n,
        "is_reconstructed": [False] * n,
        "reconstruction_method": ["none"] * n,
    }
    return pd.DataFrame(rows)


@pytest.mark.performance
def test_normalize_and_validate_throughput() -> None:
    raw = _large_candles(5_000)
    t0 = time.perf_counter()
    frame = normalize_frame(raw, SeriesKind.CANDLES)
    report = validate_series(
        frame,
        symbol="Volatility 75 Index",
        kind=SeriesKind.CANDLES,
        timeframe="M1",
        now=frame["time"].iloc[-1].to_pydatetime(),
        freshness_max_age_s=31_536_000,
    )
    elapsed = time.perf_counter() - t0
    assert len(frame) == 5_000
    assert report.row_count == 5_000
    # Soft budget: should finish well under a couple seconds on CI hosts.
    assert elapsed < 5.0, f"normalize+validate too slow: {elapsed:.3f}s"


@pytest.mark.performance
def test_parquet_write_read_throughput(tmp_path: Path) -> None:
    store = MarketDataStore(tmp_path / "data")
    frame = normalize_frame(_large_candles(5_000), SeriesKind.CANDLES)
    t0 = time.perf_counter()
    store.write_working(
        frame,
        symbol="Volatility 75 Index",
        kind=SeriesKind.CANDLES,
        timeframe="M1",
    )
    loaded = store.read_working(
        symbol="Volatility 75 Index",
        kind=SeriesKind.CANDLES,
        timeframe="M1",
    )
    elapsed = time.perf_counter() - t0
    assert len(loaded) == 5_000
    assert elapsed < 5.0, f"parquet roundtrip too slow: {elapsed:.3f}s"
