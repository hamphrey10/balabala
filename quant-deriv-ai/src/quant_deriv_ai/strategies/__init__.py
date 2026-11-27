"""Strategy Engine package — experimental hypotheses only (LOT-006).

Emits BUY/SELL/HOLD/EXIT candidate signals. No orders. No auto live activation.
"""

from __future__ import annotations

from quant_deriv_ai.strategies.agent import StrategyAgent
from quant_deriv_ai.strategies.base import BaseStrategy, StrategyError
from quant_deriv_ai.strategies.engine import StrategyEngine
from quant_deriv_ai.strategies.models import (
    SignalType,
    StrategyCategory,
    StrategySignal,
    StrategySnapshot,
    StrategySpec,
    StrategyStatus,
)
from quant_deriv_ai.strategies.registry import (
    get_strategy,
    list_strategies,
    registry_count,
    strategy_ids,
    validate_strategy,
)

__all__ = [
    "BaseStrategy",
    "SignalType",
    "StrategyAgent",
    "StrategyCategory",
    "StrategyEngine",
    "StrategyError",
    "StrategySignal",
    "StrategySnapshot",
    "StrategySpec",
    "StrategyStatus",
    "get_strategy",
    "list_strategies",
    "registry_count",
    "strategy_ids",
    "validate_strategy",
]
