"""Quantitative Research Agent — BaseAgent wrapper; never places orders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quant_deriv_ai.agents.base import AgentContext, BaseAgent
from quant_deriv_ai.core.exceptions import AgentError
from quant_deriv_ai.core.logging import get_logger
from quant_deriv_ai.quantitative.engine import QuantitativeResearchEngine

log = get_logger(__name__)


class QuantitativeResearchAgent(BaseAgent):
    """Runs stats / edge / report research actions. No execution side effects."""

    def __init__(self, context: AgentContext, engine: QuantitativeResearchEngine) -> None:
        super().__init__(context)
        self.engine = engine
        self._last_result: dict[str, Any] | None = None

    @property
    def last_result(self) -> dict[str, Any] | None:
        return self._last_result

    def run(self) -> None:
        action = str(self.context.config.get("action", "stats"))
        log.info("QuantitativeResearchAgent action={}", action)

        frame = self.context.config.get("frame")
        symbol = str(self.context.config.get("symbol", "UNKNOWN"))
        timeframe = str(self.context.config.get("timeframe", "M1"))

        if frame is None:
            raise AgentError(f"{action} requires frame in context.config")
        import pandas as pd

        if not isinstance(frame, pd.DataFrame):
            raise AgentError("frame must be a pandas DataFrame")

        lag = self.context.config.get("forward_lag")
        horizon = self.context.config.get("forward_horizon")
        raw_probes = self.context.config.get("probes")
        probes = list(raw_probes) if isinstance(raw_probes, (list, tuple)) else None

        if action == "stats":
            report = self.engine.stats(frame, symbol=symbol, timeframe=timeframe)
        elif action == "edge":
            report = self.engine.edge(
                frame,
                symbol=symbol,
                timeframe=timeframe,
                forward_lag=int(lag) if lag is not None else None,
                forward_horizon=int(horizon) if horizon is not None else None,
                probes=probes,
            )
        elif action == "report":
            out = self.context.config.get("output_path")
            fmt = str(self.context.config.get("fmt", "markdown"))
            report = self.engine.report(
                frame,
                symbol=symbol,
                timeframe=timeframe,
                forward_lag=int(lag) if lag is not None else None,
                forward_horizon=int(horizon) if horizon is not None else None,
                probes=probes,
                output_path=Path(str(out)) if out is not None else None,
                fmt=fmt,
            )
        else:
            raise AgentError(f"unsupported QuantitativeResearchAgent action: {action!r}")

        self._last_result = report.model_dump(mode="json")

    def shutdown(self) -> None:
        log.info("QuantitativeResearchAgent shutdown name={}", self.name)
