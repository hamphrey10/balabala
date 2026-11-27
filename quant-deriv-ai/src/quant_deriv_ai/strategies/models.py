"""Pydantic contracts for the Strategy Engine (LOT-006).

Strategies emit candidate signals only. No orders. No auto live activation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SignalType(StrEnum):
    """Candidate strategy signals — never executed by this package."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    EXIT = "EXIT"


class StrategyStatus(StrEnum):
    """Lifecycle status. Live / paper activation is out of scope for LOT-006."""

    HYPOTHESIS = "hypothesis"
    DRAFT = "draft"
    RESEARCH = "research"
    REJECTED = "rejected"
    RETIRED = "retired"


# Statuses that may never auto-activate (LOT-006 forbids live activation entirely).
_NON_ACTIVATABLE: frozenset[StrategyStatus] = frozenset(
    {
        StrategyStatus.HYPOTHESIS,
        StrategyStatus.DRAFT,
        StrategyStatus.RESEARCH,
        StrategyStatus.REJECTED,
        StrategyStatus.RETIRED,
    }
)


class StrategyCategory(StrEnum):
    TREND = "trend"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    FILTERED = "filtered"


class StrategySpec(BaseModel):
    """Registry entry describing one experimental strategy hypothesis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(..., min_length=1, description="Stable registry id, e.g. STR-001")
    name: str = Field(..., min_length=1)
    category: StrategyCategory
    status: StrategyStatus = StrategyStatus.HYPOTHESIS
    description: str
    hypothesis: str
    default_params: dict[str, Any] = Field(default_factory=dict)
    signals: list[SignalType] = Field(
        default_factory=lambda: [
            SignalType.BUY,
            SignalType.SELL,
            SignalType.HOLD,
            SignalType.EXIT,
        ]
    )
    requires_ohlc: bool = True
    # Explicit safety flags — LOT-006 never auto-activates.
    auto_activate: bool = False
    live_allowed: bool = False
    edge_demonstrated: bool = False
    lot_introduced: str = "LOT-006"
    notes: str = ""

    @field_validator("id")
    @classmethod
    def _normalize_id(cls, value: str) -> str:
        stripped = value.strip().upper()
        if not stripped:
            msg = "strategy id must not be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("auto_activate")
    @classmethod
    def _forbid_auto_activate(cls, value: bool) -> bool:
        if value:
            msg = "auto_activate=True is forbidden (LOT-006: no auto live activation)"
            raise ValueError(msg)
        return False

    @field_validator("live_allowed")
    @classmethod
    def _forbid_live(cls, value: bool) -> bool:
        if value:
            msg = "live_allowed=True is forbidden (DEMO / research phase)"
            raise ValueError(msg)
        return False

    @property
    def is_activatable(self) -> bool:
        """LOT-006: no status is considered activatable for live or paper auto-run."""
        return False

    @property
    def status_is_non_activatable(self) -> bool:
        return self.status in _NON_ACTIVATABLE


class StrategySignal(BaseModel):
    """One bar / snapshot signal from a strategy (candidate only)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    signal_id: str = Field(default_factory=lambda: str(uuid4()))
    strategy_id: str
    strategy_name: str
    symbol: str
    timeframe: str
    signal: SignalType
    strength: float = Field(default=0.0, ge=0.0, le=1.0)
    bar_time: datetime | None = None
    bar_index: int | None = None
    rationale: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    edge_demonstrated: bool = False
    auto_activate: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class StrategySnapshot(BaseModel):
    """Engine output for one strategy evaluation — analysis only."""

    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    strategy_name: str
    status: StrategyStatus
    symbol: str
    timeframe: str
    as_of: datetime | None = None
    bar_count: int = 0
    latest: StrategySignal | None = None
    series: list[StrategySignal] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    hypothesis: str = ""
    meta: dict[str, Any] = Field(
        default_factory=lambda: {
            "no_orders": True,
            "auto_activate": False,
            "live_allowed": False,
            "edge_demonstrated": False,
            "lot": "LOT-006",
        }
    )
