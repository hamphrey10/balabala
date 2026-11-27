"""Pydantic contracts for technical analysis snapshots (LOT-004)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TrendDirection(StrEnum):
    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


class StructureBias(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    RANGE = "range"
    UNKNOWN = "unknown"


class BreakoutSide(StrEnum):
    UP = "up"
    DOWN = "down"
    NONE = "none"


class SwingKind(StrEnum):
    HIGH = "high"
    LOW = "low"


class SwingPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: SwingKind
    index: int
    time: datetime | None = None
    price: float


class StructureLevel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str  # support | resistance
    price: float
    touches: int = 1
    source: str = "swing"


class BreakoutEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    side: BreakoutSide
    level: float
    close: float
    confirmed: bool = False
    lookback: int = 20


class TrendState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    direction: TrendDirection
    strength: float = Field(ge=0.0, le=1.0, description="0=weak/unknown, 1=strong")
    adx: float | None = None
    sma_fast: float | None = None
    sma_slow: float | None = None
    structure_bias: StructureBias = StructureBias.UNKNOWN


class MTFTimeframeView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    timeframe: str
    trend: TrendDirection
    structure_bias: StructureBias
    last_close: float | None = None
    rsi: float | None = None


class MTFConsensus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    aligned: bool
    dominant_trend: TrendDirection
    views: list[MTFTimeframeView] = Field(default_factory=list)
    notes: str = ""


class IndicatorValues(BaseModel):
    """Latest scalar values for a set of indicators (NaNs omitted)."""

    model_config = ConfigDict(extra="forbid")

    values: dict[str, float] = Field(default_factory=dict)


class VolumeCaveat(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    volume_present: bool = False
    volume_is_synthetic: bool = True
    note: str = (
        "Volume columns on Deriv synthetic indices / tick volumes must not be "
        "treated as real traded liquidity."
    )


class TechnicalSnapshot(BaseModel):
    """Standardized TA output for one symbol/timeframe (or MTF aggregate)."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    timeframe: str
    as_of: datetime | None = None
    bar_count: int = 0
    last_close: float | None = None
    indicators: dict[str, float] = Field(default_factory=dict)
    trend: TrendState = Field(
        default_factory=lambda: TrendState(direction=TrendDirection.UNKNOWN, strength=0.0)
    )
    structure_bias: StructureBias = StructureBias.UNKNOWN
    swings: list[SwingPoint] = Field(default_factory=list)
    support_resistance: list[StructureLevel] = Field(default_factory=list)
    breakout: BreakoutEvent = Field(
        default_factory=lambda: BreakoutEvent(side=BreakoutSide.NONE, level=0.0, close=0.0)
    )
    mtf: MTFConsensus | None = None
    volume: VolumeCaveat = Field(default_factory=VolumeCaveat)
    meta: dict[str, Any] = Field(default_factory=dict)
