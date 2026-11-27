"""Standardized indicator contracts — causal, vectorized, typed."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from quant_deriv_ai.core.exceptions import QuantDerivError


class IndicatorCategory(StrEnum):
    TREND = "trend"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    STRUCTURE = "structure"


class IndicatorError(QuantDerivError):
    """Raised for invalid indicator inputs or unknown indicator names."""


class IndicatorSpec(BaseModel):
    """Registry entry describing one indicator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    category: IndicatorCategory
    description: str
    default_params: dict[str, Any] = Field(default_factory=dict)
    requires_ohlc: bool = False
    requires_volume: bool = False
    # When True, callers must not treat volume as real liquidity (synthetic / tick volume).
    volume_may_be_synthetic: bool = False
    outputs: list[str] = Field(default_factory=lambda: ["value"])


IndicatorFn = Callable[..., pd.Series | pd.DataFrame]


def as_float_series(values: Any, *, name: str = "value") -> pd.Series:
    """Coerce input to a float Series (preserves index when available)."""
    if isinstance(values, pd.Series):
        return values.astype(float)
    return pd.Series(np.asarray(values, dtype=float), name=name)


def require_positive_int(name: str, value: int, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        msg = f"{name} must be an int >= {minimum}, got {value!r}"
        raise IndicatorError(msg)
    return value


def require_columns(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        msg = f"OHLC frame missing columns: {missing}"
        raise IndicatorError(msg)


def validate_params(spec: IndicatorSpec, params: Mapping[str, Any]) -> dict[str, Any]:
    """Merge defaults with overrides; reject unknown keys."""
    merged = dict(spec.default_params)
    unknown = set(params) - set(merged) - {"volume_is_synthetic"}
    # Allow volume_is_synthetic as a common optional flag for volume-aware indicators.
    if unknown and not spec.requires_volume:
        # Non-volume indicators: only known params.
        bad = set(params) - set(merged)
        if bad:
            msg = f"unknown params for {spec.name}: {sorted(bad)}"
            raise IndicatorError(msg)
    elif unknown and spec.requires_volume:
        bad = set(params) - set(merged) - {"volume_is_synthetic"}
        if bad:
            msg = f"unknown params for {spec.name}: {sorted(bad)}"
            raise IndicatorError(msg)
    for key, value in params.items():
        if key == "volume_is_synthetic":
            continue
        merged[key] = value
    return merged


def causal_rolling_mean(series: pd.Series, window: int) -> pd.Series:
    """SMA using only past and current bars (pandas rolling is causal by default)."""
    require_positive_int("window", window)
    return series.astype(float).rolling(window=window, min_periods=window).mean()


def causal_ema(series: pd.Series, span: int) -> pd.Series:
    """EMA with adjust=False (recursive, causal). Warmup NaNs for first span-1 bars."""
    require_positive_int("span", span)
    s = series.astype(float)
    ema = s.ewm(span=span, adjust=False, min_periods=span).mean()
    return ema
