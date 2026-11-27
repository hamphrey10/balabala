"""Strategy base contracts — candidate signals only (LOT-006)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

import pandas as pd

from quant_deriv_ai.core.exceptions import QuantDerivError
from quant_deriv_ai.strategies.models import SignalType, StrategySignal, StrategySpec


class StrategyError(QuantDerivError):
    """Raised for invalid strategy inputs, unknown ids, or unsafe activation."""


def require_ohlc(frame: pd.DataFrame) -> None:
    missing = [c for c in ("open", "high", "low", "close") if c not in frame.columns]
    if missing:
        msg = f"OHLC frame missing columns: {missing}"
        raise StrategyError(msg)


def validate_params(spec: StrategySpec, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Merge defaults with overrides; reject unknown keys."""
    merged = dict(spec.default_params)
    raw = dict(params or {})
    unknown = set(raw) - set(merged)
    if unknown:
        msg = f"unknown params for {spec.id}/{spec.name}: {sorted(unknown)}"
        raise StrategyError(msg)
    for key, value in raw.items():
        merged[key] = value
    return merged


def assert_not_activatable(spec: StrategySpec) -> None:
    """Hard guard — LOT-006 never auto-activates strategies."""
    if spec.auto_activate or spec.live_allowed:
        msg = f"strategy {spec.id} attempted activation — forbidden in LOT-006"
        raise StrategyError(msg)
    if spec.is_activatable:
        msg = f"strategy {spec.id} marked activatable — forbidden in LOT-006"
        raise StrategyError(msg)


class BaseStrategy(ABC):
    """Abstract strategy hypothesis. Subclasses emit SignalType series only."""

    def __init__(self, spec: StrategySpec, params: Mapping[str, Any] | None = None) -> None:
        assert_not_activatable(spec)
        self.spec = spec
        self.params = validate_params(spec, params)

    @property
    def strategy_id(self) -> str:
        return self.spec.id

    @property
    def name(self) -> str:
        return self.spec.name

    def generate(
        self,
        frame: pd.DataFrame,
        *,
        symbol: str = "UNKNOWN",
        timeframe: str = "M1",
    ) -> list[StrategySignal]:
        require_ohlc(frame)
        assert_not_activatable(self.spec)
        raw = self._compute(frame)
        if len(raw) != len(frame):
            msg = (
                f"{self.spec.id} signal length {len(raw)} != frame length {len(frame)}"
            )
            raise StrategyError(msg)
        times = frame["time"] if "time" in frame.columns else None
        out: list[StrategySignal] = []
        for i, signal in enumerate(raw):
            bar_time = None
            if times is not None:
                value = times.iloc[i]
                bar_time = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
            out.append(
                StrategySignal(
                    strategy_id=self.spec.id,
                    strategy_name=self.spec.name,
                    symbol=symbol,
                    timeframe=timeframe,
                    signal=SignalType(signal),
                    strength=self._strength(frame, i, signal),
                    bar_time=bar_time,
                    bar_index=i,
                    rationale=self._rationale(frame, i, signal),
                    params=dict(self.params),
                    edge_demonstrated=False,
                    auto_activate=False,
                    metadata={"no_orders": True, "hypothesis": True},
                )
            )
        return out

    def latest(
        self,
        frame: pd.DataFrame,
        *,
        symbol: str = "UNKNOWN",
        timeframe: str = "M1",
    ) -> StrategySignal:
        series = self.generate(frame, symbol=symbol, timeframe=timeframe)
        if not series:
            msg = f"{self.spec.id}: empty frame — no signal"
            raise StrategyError(msg)
        return series[-1]

    @abstractmethod
    def _compute(self, frame: pd.DataFrame) -> list[SignalType]:
        """Return one SignalType per bar (causal; HOLD during warmup)."""

    def _strength(self, frame: pd.DataFrame, index: int, signal: SignalType) -> float:
        if signal is SignalType.HOLD:
            return 0.0
        return 0.5

    def _rationale(self, frame: pd.DataFrame, index: int, signal: SignalType) -> str:
        return f"{self.spec.name}: {signal.value} (hypothesis; no edge demonstrated)"
