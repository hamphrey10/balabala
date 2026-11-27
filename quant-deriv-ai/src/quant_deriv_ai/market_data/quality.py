"""Data quality control: missing, duplicate, outlier, freshness, OHLC consistency.

Missing bars are reported, never fabricated. Reconstruction (if any) must already
be flagged via ``is_reconstructed`` / ``reconstruction_method`` columns.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd

from quant_deriv_ai.market_data.models import (
    QualityIssue,
    QualityIssueKind,
    QualityReport,
    SeriesKind,
)
from quant_deriv_ai.market_data.normalize import dedupe_subset
from quant_deriv_ai.market_data.sessions import intra_session_missing_times
from quant_deriv_ai.market_data.timeframes import assert_available_timeframe


def validate_series(
    frame: pd.DataFrame,
    *,
    symbol: str,
    kind: SeriesKind,
    timeframe: str | None = None,
    now: datetime | None = None,
    freshness_max_age_s: int = 300,
    outlier_zscore: float = 8.0,
    require_fresh: bool = False,
) -> QualityReport:
    """Run quality checks; never invents rows.

    ``require_fresh``: when False (default — historical/offline mode), freshness is
    still measured (``freshness_age_s`` / ``is_fresh``) but STALE does not fail
    ``ok``. When True (live / continuous update mode), staleness flips ``ok``.
    """
    report = QualityReport(symbol=symbol, kind=kind, timeframe=timeframe, row_count=len(frame))
    if frame.empty:
        report.add_issue(
            QualityIssue(kind=QualityIssueKind.MISSING, detail="series is empty", count=1)
        )
        return report

    times = pd.to_datetime(frame["time"], utc=True)
    report.first_time = times.iloc[0].to_pydatetime()
    report.last_time = times.iloc[-1].to_pydatetime()

    # Non-UTC / naive would have been normalized; still flag tz-naive leftovers.
    if getattr(times.dt, "tz", None) is None:
        report.add_issue(
            QualityIssue(kind=QualityIssueKind.NON_UTC, detail="timestamps are not UTC-aware")
        )

    # Duplicates — candles by bar time; ticks by full quote identity (not second alone).
    subset = dedupe_subset(kind)
    dup_mask = frame.duplicated(subset=subset, keep=False)
    dup_count = int(dup_mask.sum())
    report.duplicate_count = dup_count
    if dup_count:
        report.add_issue(
            QualityIssue(
                kind=QualityIssueKind.DUPLICATE,
                detail=f"{dup_count} duplicate identity rows (key={subset})",
                count=dup_count,
            )
        )

    # Reconstructed accounting
    if "is_reconstructed" in frame.columns:
        report.reconstructed_count = int(frame["is_reconstructed"].fillna(False).sum())

    # Missing bars (candles only) — intra-session gaps only; weekends/closures skipped.
    if kind is SeriesKind.CANDLES and timeframe:
        tf = assert_available_timeframe(timeframe)
        missing = intra_session_missing_times(times, timeframe=tf)
        missing_count = int(len(missing))
        report.missing_count = missing_count
        if missing_count:
            sample = list(missing[:5])
            report.add_issue(
                QualityIssue(
                    kind=QualityIssueKind.MISSING,
                    detail=(
                        f"{missing_count} intra-session missing {tf} bars "
                        f"(sample={[pd.Timestamp(t).isoformat() for t in sample]})"
                    ),
                    count=missing_count,
                    time=pd.Timestamp(sample[0]).to_pydatetime() if sample else None,
                )
            )

    # OHLC consistency
    if kind is SeriesKind.CANDLES:
        ohlc_bad = (
            (frame["high"] < frame["low"])
            | (frame["high"] < frame["open"])
            | (frame["high"] < frame["close"])
            | (frame["low"] > frame["open"])
            | (frame["low"] > frame["close"])
        )
        bad_n = int(ohlc_bad.sum())
        if bad_n:
            report.add_issue(
                QualityIssue(
                    kind=QualityIssueKind.OHLC_INCONSISTENT,
                    detail=f"{bad_n} bars with inconsistent OHLC",
                    count=bad_n,
                )
            )

    # Outliers via log-return z-score on close (candles) or mid (ticks)
    price = _price_series(frame, kind)
    outlier_idx = _outlier_indices(price, zscore=outlier_zscore)
    report.outlier_count = len(outlier_idx)
    if outlier_idx:
        t0 = times.iloc[outlier_idx[0]].to_pydatetime()
        report.add_issue(
            QualityIssue(
                kind=QualityIssueKind.OUTLIER,
                detail=f"{len(outlier_idx)} outlier returns (z>{outlier_zscore})",
                count=len(outlier_idx),
                time=t0,
            )
        )

    # Freshness — always measured; only fails ``ok`` when require_fresh=True.
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    age = (clock - report.last_time).total_seconds()
    report.freshness_age_s = age
    report.is_fresh = age <= float(freshness_max_age_s)
    if not report.is_fresh and require_fresh:
        report.add_issue(
            QualityIssue(
                kind=QualityIssueKind.STALE,
                detail=(
                    f"last observation age {age:.1f}s exceeds "
                    f"freshness_max_age_s={freshness_max_age_s}"
                ),
                time=report.last_time,
            )
        )

    # ok stays True only when no failing issues were added
    return report


def _price_series(frame: pd.DataFrame, kind: SeriesKind) -> pd.Series:
    if kind is SeriesKind.CANDLES:
        return pd.to_numeric(frame["close"], errors="coerce")
    bid = pd.to_numeric(frame["bid"], errors="coerce")
    ask = pd.to_numeric(frame["ask"], errors="coerce")
    return (bid + ask) / 2.0


def _outlier_indices(price: pd.Series, *, zscore: float) -> list[int]:
    series = price.reset_index(drop=True).replace([np.inf, -np.inf], np.nan)
    if series.dropna().shape[0] < 3:
        return []
    # Avoid log of non-positive prices.
    positive = series.where(series > 0)
    rets = np.log(positive / positive.shift(1))
    valid = rets.dropna()
    if valid.empty:
        return []
    mu = float(valid.mean())
    sigma = float(valid.std(ddof=0))
    if sigma <= 0.0 or not np.isfinite(sigma):
        return []
    z = (valid - mu) / sigma
    return [int(i) for i in z.index[np.abs(z.to_numpy()) > zscore].tolist()]
