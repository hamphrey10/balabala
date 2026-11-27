"""Pydantic contracts for market-data collection, quality, and versioning."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SeriesKind(StrEnum):
    CANDLES = "candles"
    TICKS = "ticks"


class DatasetStatus(StrEnum):
    MUTABLE = "mutable"
    IMMUTABLE = "immutable"


class ReconstructionMethod(StrEnum):
    """Explicit reconstruction methods — never silent fabrication."""

    NONE = "none"
    FORWARD_FILL = "forward_fill"
    MARK_GAP = "mark_gap"


class QualityIssueKind(StrEnum):
    MISSING = "missing"
    DUPLICATE = "duplicate"
    OUTLIER = "outlier"
    STALE = "stale"
    NON_UTC = "non_utc"
    OHLC_INCONSISTENT = "ohlc_inconsistent"


class QualityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: QualityIssueKind
    detail: str
    time: datetime | None = None
    count: int = 1


class QualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    kind: SeriesKind
    timeframe: str | None = None
    row_count: int = 0
    duplicate_count: int = 0
    missing_count: int = 0
    outlier_count: int = 0
    reconstructed_count: int = 0
    first_time: datetime | None = None
    last_time: datetime | None = None
    freshness_age_s: float | None = None
    is_fresh: bool | None = None
    issues: list[QualityIssue] = Field(default_factory=list)
    ok: bool = True

    def add_issue(self, issue: QualityIssue) -> None:
        self.issues.append(issue)
        self.ok = False


class DatasetManifest(BaseModel):
    """Immutable backtest dataset metadata (content-addressed version)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str
    version: str
    symbol: str
    kind: SeriesKind
    timeframe: str | None = None
    status: DatasetStatus = DatasetStatus.IMMUTABLE
    created_at: datetime
    content_hash: str
    row_count: int
    first_time: datetime | None = None
    last_time: datetime | None = None
    source: str = "mt5"
    reconstruction_method: ReconstructionMethod = ReconstructionMethod.NONE
    notes: str = ""
    quality_ok: bool = True
    extra: dict[str, Any] = Field(default_factory=dict)


class SeriesStats(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    kind: SeriesKind
    timeframe: str | None = None
    row_count: int
    first_time: datetime | None = None
    last_time: datetime | None = None
    parquet_bytes: int = 0
    content_hash: str | None = None
    version: str | None = None
    status: DatasetStatus | None = None


class DownloadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    kind: SeriesKind
    timeframe: str | None = None
    rows_fetched: int = 0
    rows_written: int = 0
    rows_deduped: int = 0
    first_time: datetime | None = None
    last_time: datetime | None = None
    quality: QualityReport | None = None
    version: str | None = None


class UpdateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    kind: SeriesKind
    timeframe: str | None = None
    rows_added: int = 0
    from_time: datetime | None = None
    to_time: datetime | None = None
    quality: QualityReport | None = None
