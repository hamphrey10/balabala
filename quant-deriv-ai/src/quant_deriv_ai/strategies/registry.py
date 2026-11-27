"""Strategy Registry — discovery, inspect, validate (LOT-006).

No auto live activation. No order placement.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from quant_deriv_ai.strategies.base import (
    BaseStrategy,
    StrategyError,
    assert_not_activatable,
    validate_params,
)
from quant_deriv_ai.strategies.catalog import all_strategy_specs, build_strategy
from quant_deriv_ai.strategies.models import StrategyCategory, StrategySpec, StrategyStatus

_REGISTRY: dict[str, StrategySpec] = {spec.id: spec for spec in all_strategy_specs()}
_BY_NAME: dict[str, StrategySpec] = {spec.name.lower(): spec for spec in _REGISTRY.values()}


def list_strategies(
    *,
    status: StrategyStatus | str | None = None,
    category: StrategyCategory | str | None = None,
) -> list[StrategySpec]:
    """Return registered strategy specs sorted by id."""
    specs = [_REGISTRY[k] for k in sorted(_REGISTRY)]
    if status is not None:
        st = StrategyStatus(status) if not isinstance(status, StrategyStatus) else status
        specs = [s for s in specs if s.status is st]
    if category is not None:
        cat = (
            StrategyCategory(category)
            if not isinstance(category, StrategyCategory)
            else category
        )
        specs = [s for s in specs if s.category is cat]
    return specs


def get_strategy(key: str) -> StrategySpec:
    """Lookup by id (STR-001) or name (sma_crossover)."""
    raw = key.strip()
    if not raw:
        msg = "strategy key must not be empty"
        raise StrategyError(msg)
    upper = raw.upper()
    if upper in _REGISTRY:
        return _REGISTRY[upper]
    lower = raw.lower()
    if lower in _BY_NAME:
        return _BY_NAME[lower]
    msg = f"unknown strategy: {key!r}; known ids: {sorted(_REGISTRY)}"
    raise StrategyError(msg)


def strategy_ids() -> list[str]:
    return sorted(_REGISTRY)


def strategy_names() -> list[str]:
    return sorted(s.name for s in _REGISTRY.values())


def validate_strategy(
    key: str,
    params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate strategy id/name + params; return merged params.

    Also enforces LOT-006 activation guards (no auto-activate / no live).
    """
    spec = get_strategy(key)
    assert_not_activatable(spec)
    if spec.edge_demonstrated:
        # Hypotheses in this lot must not claim demonstrated edge.
        msg = f"strategy {spec.id} claims edge_demonstrated — forbidden until research gates pass"
        raise StrategyError(msg)
    return validate_params(spec, params)


def instantiate(
    key: str,
    params: Mapping[str, Any] | None = None,
) -> BaseStrategy:
    """Build a strategy instance from the registry (signals only)."""
    spec = get_strategy(key)
    assert_not_activatable(spec)
    return build_strategy(spec, params)


def registry_count() -> int:
    return len(_REGISTRY)


def assert_hypothesis_only() -> None:
    """Invariant: every registered strategy is a non-activatable hypothesis."""
    for spec in _REGISTRY.values():
        assert_not_activatable(spec)
        if spec.status is not StrategyStatus.HYPOTHESIS:
            msg = f"{spec.id} status={spec.status.value}; LOT-006 expects hypothesis"
            raise StrategyError(msg)
        if spec.auto_activate or spec.live_allowed or spec.edge_demonstrated:
            msg = f"{spec.id} violates LOT-006 safety flags"
            raise StrategyError(msg)
    if len(_REGISTRY) != 12:
        msg = f"expected 12 experimental strategies, found {len(_REGISTRY)}"
        raise StrategyError(msg)
