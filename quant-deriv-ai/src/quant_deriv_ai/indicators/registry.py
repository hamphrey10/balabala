"""Indicator registry — discovery, listing, and parameter validation."""

from __future__ import annotations

from typing import Any

from quant_deriv_ai.indicators.base import (
    IndicatorCategory,
    IndicatorError,
    IndicatorSpec,
    validate_params,
)

_REGISTRY: dict[str, IndicatorSpec] = {
    "sma": IndicatorSpec(
        name="sma",
        category=IndicatorCategory.TREND,
        description="Simple moving average of close",
        default_params={"period": 20},
        outputs=["sma"],
    ),
    "ema": IndicatorSpec(
        name="ema",
        category=IndicatorCategory.TREND,
        description="Exponential moving average of close",
        default_params={"period": 20},
        outputs=["ema"],
    ),
    "rsi": IndicatorSpec(
        name="rsi",
        category=IndicatorCategory.MOMENTUM,
        description="Relative Strength Index (Wilder)",
        default_params={"period": 14},
        outputs=["rsi"],
    ),
    "macd": IndicatorSpec(
        name="macd",
        category=IndicatorCategory.TREND,
        description="MACD line, signal, and histogram",
        default_params={"fast": 12, "slow": 26, "signal": 9},
        outputs=["macd", "macd_signal", "macd_hist"],
    ),
    "atr": IndicatorSpec(
        name="atr",
        category=IndicatorCategory.VOLATILITY,
        description="Average True Range (Wilder)",
        default_params={"period": 14},
        requires_ohlc=True,
        outputs=["atr"],
    ),
    "adx": IndicatorSpec(
        name="adx",
        category=IndicatorCategory.TREND,
        description="Average Directional Index with +DI/-DI",
        default_params={"period": 14},
        requires_ohlc=True,
        outputs=["adx", "plus_di", "minus_di"],
    ),
    "bollinger": IndicatorSpec(
        name="bollinger",
        category=IndicatorCategory.VOLATILITY,
        description="Bollinger Bands (SMA mid ± std)",
        default_params={"period": 20, "num_std": 2.0},
        outputs=["bb_mid", "bb_upper", "bb_lower", "bb_width"],
    ),
    "stochastic": IndicatorSpec(
        name="stochastic",
        category=IndicatorCategory.MOMENTUM,
        description="Stochastic oscillator %K / %D",
        default_params={"k_period": 14, "d_period": 3},
        requires_ohlc=True,
        outputs=["stoch_k", "stoch_d"],
    ),
    "donchian": IndicatorSpec(
        name="donchian",
        category=IndicatorCategory.VOLATILITY,
        description="Donchian channel (rolling high/low)",
        default_params={"period": 20},
        requires_ohlc=True,
        outputs=["donchian_upper", "donchian_mid", "donchian_lower"],
    ),
    "roc": IndicatorSpec(
        name="roc",
        category=IndicatorCategory.MOMENTUM,
        description="Rate of Change (%)",
        default_params={"period": 12},
        outputs=["roc"],
    ),
    "momentum": IndicatorSpec(
        name="momentum",
        category=IndicatorCategory.MOMENTUM,
        description="Close momentum (close - close[n])",
        default_params={"period": 10},
        outputs=["momentum"],
    ),
    "cci": IndicatorSpec(
        name="cci",
        category=IndicatorCategory.MOMENTUM,
        description="Commodity Channel Index",
        default_params={"period": 20},
        requires_ohlc=True,
        outputs=["cci"],
    ),
    "williams_r": IndicatorSpec(
        name="williams_r",
        category=IndicatorCategory.MOMENTUM,
        description="Williams %R",
        default_params={"period": 14},
        requires_ohlc=True,
        outputs=["williams_r"],
    ),
    "hist_vol": IndicatorSpec(
        name="hist_vol",
        category=IndicatorCategory.VOLATILITY,
        description="Historical volatility of log returns",
        default_params={"period": 20, "annualize": False, "periods_per_year": 252},
        outputs=["hist_vol"],
    ),
}


def list_indicators() -> list[IndicatorSpec]:
    """Return all registered indicator specs sorted by name."""
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


def get_indicator(name: str) -> IndicatorSpec:
    key = name.strip().lower()
    if key not in _REGISTRY:
        msg = f"unknown indicator: {name!r}; known: {sorted(_REGISTRY)}"
        raise IndicatorError(msg)
    return _REGISTRY[key]


def validate_indicator(name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate indicator name + params; return merged params."""
    spec = get_indicator(name)
    return validate_params(spec, params or {})


def indicator_names() -> list[str]:
    return sorted(_REGISTRY)
