"""Strategy registry — 12 hypotheses, list / validate / safety."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from quant_deriv_ai.strategies.base import StrategyError
from quant_deriv_ai.strategies.models import SignalType, StrategySpec, StrategyStatus
from quant_deriv_ai.strategies.registry import (
    assert_hypothesis_only,
    get_strategy,
    list_strategies,
    registry_count,
    strategy_ids,
    strategy_names,
    validate_strategy,
)

REQUIRED_IDS = [f"STR-{i:03d}" for i in range(1, 13)]
REQUIRED_NAMES = [
    "sma_crossover",
    "ema_crossover",
    "rsi_mean_reversion",
    "macd_cross",
    "bollinger_reversion",
    "donchian_breakout",
    "momentum_follow",
    "adx_trend",
    "stochastic_reversion",
    "atr_breakout",
    "dual_ma_rsi_filter",
    "williams_r_reversion",
]


def test_exactly_twelve_hypotheses() -> None:
    assert registry_count() == 12
    assert strategy_ids() == REQUIRED_IDS
    assert set(strategy_names()) == set(REQUIRED_NAMES)
    assert_hypothesis_only()


def test_all_hypothesis_status_and_safety() -> None:
    for spec in list_strategies():
        assert spec.status is StrategyStatus.HYPOTHESIS
        assert spec.auto_activate is False
        assert spec.live_allowed is False
        assert spec.edge_demonstrated is False
        assert spec.is_activatable is False
        assert set(spec.signals) == {
            SignalType.BUY,
            SignalType.SELL,
            SignalType.HOLD,
            SignalType.EXIT,
        }


def test_get_by_id_and_name() -> None:
    by_id = get_strategy("STR-003")
    by_name = get_strategy("rsi_mean_reversion")
    assert by_id.id == by_name.id == "STR-003"


def test_validate_merges_defaults() -> None:
    merged = validate_strategy("STR-001", {})
    assert merged["fast"] == 10
    assert merged["slow"] == 30
    merged2 = validate_strategy("sma_crossover", {"fast": 5})
    assert merged2["fast"] == 5
    assert merged2["slow"] == 30


def test_validate_rejects_unknown_param() -> None:
    with pytest.raises(StrategyError, match="unknown params"):
        validate_strategy("STR-001", {"fast": 5, "bogus": 1})


def test_get_unknown() -> None:
    with pytest.raises(StrategyError, match="unknown strategy"):
        get_strategy("not_a_strategy")


def test_spec_rejects_auto_activate() -> None:
    from quant_deriv_ai.strategies.models import StrategyCategory

    with pytest.raises(ValidationError):
        StrategySpec(
            id="STR-999",
            name="bad",
            category=StrategyCategory.TREND,
            description="x",
            hypothesis="y",
            auto_activate=True,
        )


def test_list_filter_status() -> None:
    hyps = list_strategies(status="hypothesis")
    assert len(hyps) == 12
    assert list_strategies(status=StrategyStatus.REJECTED) == []
