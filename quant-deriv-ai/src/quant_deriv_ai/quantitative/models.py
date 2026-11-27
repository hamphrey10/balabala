"""Pydantic contracts for quantitative research (LOT-005)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EdgeVerdict(StrEnum):
    """Research-only edge classification — not a trading authorization."""

    INSUFFICIENT_DATA = "insufficient_data"
    NO_EDGE = "no_edge"
    WEAK = "weak"
    CANDIDATE = "candidate"
    UNKNOWN = "unknown"


class CausalityStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"


class DescriptiveStats(BaseModel):
    """Scalar descriptive statistics for one series."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    count: int
    mean: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    median: float | None = None
    p05: float | None = None
    p25: float | None = None
    p75: float | None = None
    p95: float | None = None
    skew: float | None = None
    kurtosis: float | None = None  # excess kurtosis
    missing: int = 0


class AutocorrPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lag: int = Field(ge=1)
    value: float | None = None


class ReturnStats(BaseModel):
    """Return-series summary (research only)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: str  # log | simple
    bar_count: int
    return_count: int
    descriptive: DescriptiveStats
    autocorr: list[AutocorrPoint] = Field(default_factory=list)
    hit_rate_positive: float | None = None
    annualized_vol: float | None = None
    annualization_factor: float = 252.0


class EdgeMetrics(BaseModel):
    """Causal signal vs forward-return edge metrics (research probes only)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    probe_name: str
    forward_lag: int = Field(ge=1, description="Bars between signal and forward return start")
    forward_horizon: int = Field(ge=1, description="Bars spanned by forward return")
    observations: int = 0
    active_signals: int = 0
    abstain_rate: float | None = None
    hit_rate: float | None = None
    expectancy: float | None = None
    profit_factor: float | None = None
    avg_win: float | None = None
    avg_loss: float | None = None
    sharpe: float | None = Field(
        default=None,
        description="Per-active-signal mean/std of signed PnL (not calendar-annualized)",
    )
    max_drawdown: float | None = Field(
        default=None,
        description="Max drawdown of cumsum(signed PnL) with HWM seeded at 0",
    )
    mean_forward_return: float | None = None
    verdict: EdgeVerdict = EdgeVerdict.UNKNOWN
    notes: str = ""


class CausalityCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    status: CausalityStatus
    detail: str = ""


class ResearchReport(BaseModel):
    """Standardized quantitative research output (no orders)."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    timeframe: str
    as_of: datetime | None = None
    bar_count: int = 0
    generated_at: datetime | None = None
    returns: ReturnStats | None = None
    price_stats: DescriptiveStats | None = None
    edge_probes: list[EdgeMetrics] = Field(default_factory=list)
    causality: list[CausalityCheck] = Field(default_factory=list)
    summary: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)
