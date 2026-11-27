"""Technical indicators library (LOT-004) — vectorized, causal, typed."""

from __future__ import annotations

from quant_deriv_ai.indicators.base import (
    IndicatorCategory,
    IndicatorError,
    IndicatorSpec,
)
from quant_deriv_ai.indicators.core import (
    adx,
    atr,
    bollinger,
    cci,
    compute_from_ohlc,
    donchian,
    ema,
    historical_volatility,
    macd,
    momentum,
    roc,
    rsi,
    sma,
    stochastic,
    williams_r,
)
from quant_deriv_ai.indicators.registry import (
    get_indicator,
    indicator_names,
    list_indicators,
    validate_indicator,
)

__all__ = [
    "IndicatorCategory",
    "IndicatorError",
    "IndicatorSpec",
    "adx",
    "atr",
    "bollinger",
    "cci",
    "compute_from_ohlc",
    "donchian",
    "ema",
    "get_indicator",
    "historical_volatility",
    "indicator_names",
    "list_indicators",
    "macd",
    "momentum",
    "roc",
    "rsi",
    "sma",
    "stochastic",
    "validate_indicator",
    "williams_r",
]
