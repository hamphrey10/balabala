"""Indicator registry list / validate."""

from __future__ import annotations

import pytest

from quant_deriv_ai.indicators.base import IndicatorError
from quant_deriv_ai.indicators.registry import (
    get_indicator,
    indicator_names,
    list_indicators,
    validate_indicator,
)

REQUIRED = [
    "sma",
    "ema",
    "rsi",
    "macd",
    "atr",
    "adx",
    "bollinger",
    "stochastic",
    "donchian",
    "roc",
    "momentum",
    "cci",
    "williams_r",
    "hist_vol",
]


def test_all_required_indicators_registered() -> None:
    names = indicator_names()
    for name in REQUIRED:
        assert name in names
    assert len(list_indicators()) == len(names)


def test_validate_merges_defaults() -> None:
    merged = validate_indicator("rsi", {})
    assert merged["period"] == 14
    merged2 = validate_indicator("rsi", {"period": 7})
    assert merged2["period"] == 7


def test_validate_rejects_unknown_param() -> None:
    with pytest.raises(IndicatorError, match="unknown"):
        validate_indicator("sma", {"period": 10, "bogus": 1})


def test_get_unknown() -> None:
    with pytest.raises(IndicatorError, match="unknown indicator"):
        get_indicator("not_an_indicator")
