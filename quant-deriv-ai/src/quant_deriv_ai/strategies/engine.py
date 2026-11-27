"""Strategy Engine — generate candidate signals only (LOT-006).

Never places orders. Never auto-activates strategies for live trading.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from quant_deriv_ai.core.exceptions import QuantDerivError
from quant_deriv_ai.core.logging import get_logger
from quant_deriv_ai.market_data.models import SeriesKind
from quant_deriv_ai.persistence.store import MarketDataStore
from quant_deriv_ai.strategies.base import assert_not_activatable
from quant_deriv_ai.strategies.models import StrategySignal, StrategySnapshot
from quant_deriv_ai.strategies.registry import (
    assert_hypothesis_only,
    get_strategy,
    instantiate,
    list_strategies,
    validate_strategy,
)

log = get_logger(__name__)


class StrategyEngineError(QuantDerivError):
    """Raised for strategy engine failures."""


class StrategyEngine:
    """Evaluate registered strategy hypotheses against OHLC frames.

    Boundaries:
    - emits BUY/SELL/HOLD/EXIT candidate signals only
    - no order APIs
    - no auto live activation
    """

    def __init__(self, *, include_series: bool = False) -> None:
        assert_hypothesis_only()
        self.include_series = include_series

    @classmethod
    def from_config(cls, cfg: Mapping[str, Any] | None = None) -> StrategyEngine:
        raw = dict(cfg or {})
        return cls(include_series=bool(raw.get("include_series", False)))

    def list_registered(self) -> list[dict[str, Any]]:
        return [s.model_dump(mode="json") for s in list_strategies()]

    def inspect(self, key: str) -> dict[str, Any]:
        spec = get_strategy(key)
        assert_not_activatable(spec)
        payload = spec.model_dump(mode="json")
        payload["activatable"] = False
        payload["safety"] = {
            "no_orders": True,
            "auto_activate": False,
            "live_allowed": False,
            "edge_demonstrated": spec.edge_demonstrated,
        }
        return payload

    def validate(self, key: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        merged = validate_strategy(key, params)
        spec = get_strategy(key)
        return {
            "ok": True,
            "id": spec.id,
            "name": spec.name,
            "params": merged,
            "status": spec.status.value,
            "auto_activate": False,
            "live_allowed": False,
            "edge_demonstrated": False,
            "no_orders": True,
        }

    def evaluate(
        self,
        key: str,
        frame: pd.DataFrame,
        *,
        symbol: str = "UNKNOWN",
        timeframe: str = "M1",
        params: Mapping[str, Any] | None = None,
        include_series: bool | None = None,
    ) -> StrategySnapshot:
        """Run one strategy hypothesis; return snapshot (no orders)."""
        if frame.empty:
            raise StrategyEngineError("empty OHLC frame")
        spec = get_strategy(key)
        assert_not_activatable(spec)
        strategy = instantiate(spec.id, params)
        series = strategy.generate(frame, symbol=symbol, timeframe=timeframe)
        latest: StrategySignal | None = series[-1] if series else None
        as_of = None
        if "time" in frame.columns and len(frame):
            value = frame["time"].iloc[-1]
            as_of = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
        keep_series = self.include_series if include_series is None else include_series
        snap = StrategySnapshot(
            strategy_id=spec.id,
            strategy_name=spec.name,
            status=spec.status,
            symbol=symbol,
            timeframe=timeframe,
            as_of=as_of if isinstance(as_of, datetime) else datetime.now(UTC),
            bar_count=len(frame),
            latest=latest,
            series=series if keep_series else [],
            params=dict(strategy.params),
            hypothesis=spec.hypothesis,
            meta={
                "no_orders": True,
                "auto_activate": False,
                "live_allowed": False,
                "edge_demonstrated": False,
                "lot": "LOT-006",
            },
        )
        log.info(
            "strategy evaluate id={} symbol={} tf={} latest={}",
            spec.id,
            symbol,
            timeframe,
            latest.signal.value if latest else None,
        )
        return snap

    def evaluate_many(
        self,
        frame: pd.DataFrame,
        *,
        symbol: str = "UNKNOWN",
        timeframe: str = "M1",
        keys: Sequence[str] | None = None,
        include_series: bool = False,
    ) -> list[StrategySnapshot]:
        targets = list(keys) if keys else [s.id for s in list_strategies()]
        return [
            self.evaluate(
                key,
                frame,
                symbol=symbol,
                timeframe=timeframe,
                include_series=include_series,
            )
            for key in targets
        ]

    def evaluate_from_store(
        self,
        data_root: Path | str,
        *,
        key: str,
        symbol: str,
        timeframe: str = "H1",
        params: Mapping[str, Any] | None = None,
        include_series: bool | None = None,
    ) -> StrategySnapshot:
        store = MarketDataStore(Path(data_root))
        try:
            frame = store.read_working(
                symbol=symbol, kind=SeriesKind.CANDLES, timeframe=timeframe
            )
        except Exception as exc:  # PersistenceError / FileNotFound
            raise StrategyEngineError(
                f"no working candles for {symbol}/{timeframe} under {data_root}: {exc}"
            ) from exc
        if frame.empty:
            raise StrategyEngineError(
                f"empty working candles for {symbol}/{timeframe} under {data_root}"
            )
        return self.evaluate(
            key,
            frame,
            symbol=symbol,
            timeframe=timeframe,
            params=params,
            include_series=include_series,
        )
