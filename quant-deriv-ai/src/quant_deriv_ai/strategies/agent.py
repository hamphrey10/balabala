"""Strategy Agent — BaseAgent wrapper; never places orders (LOT-006)."""

from __future__ import annotations

from typing import Any

from quant_deriv_ai.agents.base import AgentContext, BaseAgent
from quant_deriv_ai.core.exceptions import AgentError
from quant_deriv_ai.core.logging import get_logger
from quant_deriv_ai.strategies.engine import StrategyEngine

log = get_logger(__name__)


class StrategyAgent(BaseAgent):
    """Runs list / inspect / validate / evaluate actions. No execution side effects."""

    def __init__(self, context: AgentContext, engine: StrategyEngine) -> None:
        super().__init__(context)
        self.engine = engine
        self._last_result: dict[str, Any] | None = None

    @property
    def last_result(self) -> dict[str, Any] | None:
        return self._last_result

    def run(self) -> None:
        action = str(self.context.config.get("action", "list"))
        log.info("StrategyAgent action={}", action)

        if action == "list":
            self._last_result = {
                "strategies": self.engine.list_registered(),
                "no_orders": True,
            }
            return

        key = self.context.config.get("strategy")
        if action in {"inspect", "validate", "evaluate"} and not key:
            raise AgentError(f"{action} requires strategy in context.config")

        if action == "inspect":
            self._last_result = self.engine.inspect(str(key))
            return

        if action == "validate":
            raw_params = self.context.config.get("params")
            params = dict(raw_params) if isinstance(raw_params, dict) else None
            self._last_result = self.engine.validate(str(key), params)
            return

        if action == "evaluate":
            frame = self.context.config.get("frame")
            if frame is None:
                raise AgentError("evaluate requires frame in context.config")
            import pandas as pd

            if not isinstance(frame, pd.DataFrame):
                raise AgentError("frame must be a pandas DataFrame")
            symbol = str(self.context.config.get("symbol", "UNKNOWN"))
            timeframe = str(self.context.config.get("timeframe", "M1"))
            raw_params = self.context.config.get("params")
            params = dict(raw_params) if isinstance(raw_params, dict) else None
            snap = self.engine.evaluate(
                str(key),
                frame,
                symbol=symbol,
                timeframe=timeframe,
                params=params,
            )
            self._last_result = snap.model_dump(mode="json")
            return

        raise AgentError(f"unsupported StrategyAgent action: {action!r}")

    def shutdown(self) -> None:
        log.info("StrategyAgent shutdown name={}", self.name)
