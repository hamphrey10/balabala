"""Quality-control tests: missing / duplicate / outlier / freshness / no fabrication."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from quant_deriv_ai.market_data.models import QualityIssueKind, ReconstructionMethod, SeriesKind
from quant_deriv_ai.market_data.normalize import normalize_frame
from quant_deriv_ai.market_data.quality import validate_series
from quant_deriv_ai.market_data.reconstruct import (
    ReconstructionForbiddenError,
    reconstruct_candles,
)


def _candles(times: list[datetime], closes: list[float] | None = None) -> pd.DataFrame:
    closes = closes or [100.0 + i for i in range(len(times))]
    rows = []
    for i, t in enumerate(times):
        c = closes[i]
        rows.append(
            {
                "symbol": "EURUSD",
                "timeframe": "M1",
                "time": t,
                "open": c,
                "high": c + 0.1,
                "low": c - 0.1,
                "close": c,
                "tick_volume": 10,
                "spread": 1,
                "real_volume": 0,
                "is_reconstructed": False,
                "reconstruction_method": "none",
            }
        )
    return normalize_frame(pd.DataFrame(rows), SeriesKind.CANDLES)


def test_detects_missing_bars() -> None:
    start = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    times = [start, start + timedelta(minutes=1), start + timedelta(minutes=3)]
    frame = _candles(times)
    report = validate_series(
        frame,
        symbol="EURUSD",
        kind=SeriesKind.CANDLES,
        timeframe="M1",
        now=start + timedelta(minutes=3),
        freshness_max_age_s=10_000,
    )
    assert report.missing_count == 1
    assert any(i.kind is QualityIssueKind.MISSING for i in report.issues)
    assert report.ok is False


def test_detects_duplicates() -> None:
    start = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    times = [start, start, start + timedelta(minutes=1)]
    frame = _candles(times)
    # Force duplicates back in (normalize doesn't drop duplicates)
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    report = validate_series(
        frame,
        symbol="EURUSD",
        kind=SeriesKind.CANDLES,
        timeframe="M1",
        now=start + timedelta(minutes=1),
        freshness_max_age_s=10_000,
    )
    assert report.duplicate_count >= 2
    assert any(i.kind is QualityIssueKind.DUPLICATE for i in report.issues)


def test_detects_outlier() -> None:
    start = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    times = [start + timedelta(minutes=i) for i in range(20)]
    closes = [100.0] * 19 + [10_000.0]
    frame = _candles(times, closes)
    report = validate_series(
        frame,
        symbol="EURUSD",
        kind=SeriesKind.CANDLES,
        timeframe="M1",
        now=times[-1],
        freshness_max_age_s=10_000,
        outlier_zscore=3.0,
    )
    assert report.outlier_count >= 1
    assert any(i.kind is QualityIssueKind.OUTLIER for i in report.issues)


def test_freshness_stale_requires_flag() -> None:
    start = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    frame = _candles([start, start + timedelta(minutes=1)])
    # Historical / default: measure freshness but do not fail ok.
    historical = validate_series(
        frame,
        symbol="EURUSD",
        kind=SeriesKind.CANDLES,
        timeframe="M1",
        now=start + timedelta(hours=1),
        freshness_max_age_s=60,
        require_fresh=False,
    )
    assert historical.is_fresh is False
    assert historical.ok is True
    assert not any(i.kind is QualityIssueKind.STALE for i in historical.issues)
    # Live mode: staleness fails the report.
    live = validate_series(
        frame,
        symbol="EURUSD",
        kind=SeriesKind.CANDLES,
        timeframe="M1",
        now=start + timedelta(hours=1),
        freshness_max_age_s=60,
        require_fresh=True,
    )
    assert live.is_fresh is False
    assert live.ok is False
    assert any(i.kind is QualityIssueKind.STALE for i in live.issues)


def test_weekend_gap_not_missing() -> None:
    # Friday 21:00 → Monday 01:00 — session break, not missing M1 bars.
    friday = datetime(2024, 1, 5, 21, 0, tzinfo=UTC)  # Friday
    monday = datetime(2024, 1, 8, 1, 0, tzinfo=UTC)  # Monday
    frame = _candles([friday, monday], closes=[100.0, 101.0])
    report = validate_series(
        frame,
        symbol="EURUSD",
        kind=SeriesKind.CANDLES,
        timeframe="M1",
        now=monday,
        freshness_max_age_s=60,
        require_fresh=False,
    )
    assert report.missing_count == 0
    assert not any(i.kind is QualityIssueKind.MISSING for i in report.issues)


def test_reconstruction_forbidden_by_default() -> None:
    start = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    times = [start, start + timedelta(minutes=1), start + timedelta(minutes=3)]
    frame = _candles(times)
    with pytest.raises(ReconstructionForbiddenError):
        reconstruct_candles(
            frame,
            timeframe="M1",
            method=ReconstructionMethod.FORWARD_FILL,
            allow=False,
        )


def test_controlled_forward_fill_marks_rows() -> None:
    start = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    times = [start, start + timedelta(minutes=1), start + timedelta(minutes=3)]
    frame = _candles(times)
    filled = reconstruct_candles(
        frame,
        timeframe="M1",
        method=ReconstructionMethod.FORWARD_FILL,
        allow=True,
    )
    assert len(filled) == 4
    reconstructed = filled[filled["is_reconstructed"]]
    assert len(reconstructed) == 1
    assert (reconstructed["reconstruction_method"] == "forward_fill").all()
    # Original rows remain unmarked
    assert int((~filled["is_reconstructed"]).sum()) == 3


def test_reconstruction_skips_weekend_closure() -> None:
    friday = datetime(2024, 1, 5, 21, 0, tzinfo=UTC)
    monday = datetime(2024, 1, 8, 1, 0, tzinfo=UTC)
    frame = _candles([friday, monday], closes=[100.0, 101.0])
    filled = reconstruct_candles(
        frame,
        timeframe="M1",
        method=ReconstructionMethod.FORWARD_FILL,
        allow=True,
    )
    assert len(filled) == 2
    assert int(filled["is_reconstructed"].sum()) == 0
