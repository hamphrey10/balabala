"""Technical Analysis Agent — BaseAgent wrapper; never places orders."""

from __future__ import annotations

from typing import Any

from quant_deriv_ai.agents.base import AgentContext, BaseAgent
from quant_deriv_ai.core.exceptions import AgentError
from quant_deriv_ai.core.logging import get_logger
from quant_deriv_ai.technical.engine import TechnicalAnalysisEngine

log = get_logger(__name__)


class TechnicalAnalysisAgent(BaseAgent):
    """Runs TA analysis / indicator listing. No execution side effects."""

    def __init__(self, context: AgentContext, engine: TechnicalAnalysisEngine) -> None:
        super().__init__(context)
        self.engine = engine
        self._last_result: dict[str, Any] | None = None

    @property
    def last_result(self) -> dict[str, Any] | None:
        return self._last_result

    def run(self) -> None:
        action = str(self.context.config.get("action", "analyze"))
        log.info("TechnicalAnalysisAgent action={}", action)

        if action == "list_indicators":
            self._last_result = {"indicators": self.engine.list_indicators()}
            return

        if action == "analyze":
            frame = self.context.config.get("frame")
            symbol = self.context.config.get("symbol", "UNKNOWN")
            timeframe = self.context.config.get("timeframe", "M1")
            if frame is None:
                raise AgentError("analyze requires frame in context.config")
            import pandas as pd

            if not isinstance(frame, pd.DataFrame):
                raise AgentError("frame must be a pandas DataFrame")
            raw_indicators = self.context.config.get("indicators")
            indicators = list(raw_indicators) if isinstance(raw_indicators, (list, tuple)) else None
            raw_mtf = self.context.config.get("mtf_frames")
            mtf_frames = raw_mtf if isinstance(raw_mtf, dict) else None
            snap = self.engine.analyze(
                frame,
                symbol=str(symbol),
                timeframe=str(timeframe),
                indicators=indicators,
                mtf_frames=mtf_frames,
            )
            self._last_result = snap.model_dump(mode="json")
            return

        raise AgentError(f"unsupported TechnicalAnalysisAgent action: {action!r}")

    def shutdown(self) -> None:
        log.info("TechnicalAnalysisAgent shutdown name={}", self.name)
