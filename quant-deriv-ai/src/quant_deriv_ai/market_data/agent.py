"""Market Data Agent — BaseAgent wrapper around MarketDataEngine."""

from __future__ import annotations

from typing import Any

from quant_deriv_ai.agents.base import AgentContext, BaseAgent
from quant_deriv_ai.core.exceptions import AgentError
from quant_deriv_ai.core.logging import get_logger
from quant_deriv_ai.market_data.engine import MarketDataEngine

log = get_logger(__name__)


class MarketDataAgent(BaseAgent):
    """Collects / validates / stores market data. Never places orders."""

    def __init__(self, context: AgentContext, engine: MarketDataEngine) -> None:
        super().__init__(context)
        self.engine = engine
        self._last_result: dict[str, Any] | None = None

    @property
    def last_result(self) -> dict[str, Any] | None:
        return self._last_result

    def run(self) -> None:
        """Execute the action described in ``context.config``."""
        action = str(self.context.config.get("action", "stats"))
        symbol = self.context.config.get("symbol")
        log.info("MarketDataAgent action={} symbol={}", action, symbol)

        if action == "stats":
            stats = self.engine.stats(symbol=symbol if isinstance(symbol, str) else None)
            self._last_result = {"stats": [s.model_dump(mode="json") for s in stats]}
            return

        if action == "validate":
            if not isinstance(symbol, str):
                raise AgentError("validate requires symbol")
            kind = self.context.config.get("kind", "candles")
            timeframe = self.context.config.get("timeframe")
            from quant_deriv_ai.market_data.models import SeriesKind

            report = self.engine.validate(
                symbol,
                SeriesKind(str(kind)),
                timeframe=str(timeframe) if timeframe else None,
            )
            self._last_result = report.model_dump(mode="json")
            return

        if action == "inspect":
            if not isinstance(symbol, str):
                raise AgentError("inspect requires symbol")
            kind = self.context.config.get("kind", "candles")
            timeframe = self.context.config.get("timeframe")
            from quant_deriv_ai.market_data.models import SeriesKind

            self._last_result = self.engine.inspect(
                symbol,
                SeriesKind(str(kind)),
                timeframe=str(timeframe) if timeframe else None,
            )
            return

        msg = f"unsupported MarketDataAgent action: {action!r}"
        raise AgentError(msg)

    def shutdown(self) -> None:
        log.info("MarketDataAgent shutdown name={}", self.name)
