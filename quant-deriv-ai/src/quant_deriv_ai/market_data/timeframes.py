"""MT5 candle timeframes used by the market-data engine.

Values match the MetaTrader5 TIMEFRAME enumeration. The engine advertises the
subset actually requested for Deriv MT5 work: M1, M5, M15, M30, H1, H4, D1.
"""

from __future__ import annotations

from datetime import timedelta

from quant_deriv_ai.execution.mt5.constants import TIMEFRAME_NAME_TO_CODE

# Timeframes actually available / used for market-data collection in LOT-003.
AVAILABLE_TIMEFRAMES: tuple[str, ...] = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")

_TIMEFRAME_DELTAS: dict[str, timedelta] = {
    "M1": timedelta(minutes=1),
    "M5": timedelta(minutes=5),
    "M15": timedelta(minutes=15),
    "M30": timedelta(minutes=30),
    "H1": timedelta(hours=1),
    "H4": timedelta(hours=4),
    "D1": timedelta(days=1),
}


def normalize_timeframe(name: str) -> str:
    """Normalize a timeframe label to upper-case canonical form."""
    key = name.strip().upper()
    if key not in TIMEFRAME_NAME_TO_CODE:
        msg = f"unknown timeframe: {name!r}"
        raise ValueError(msg)
    return key


def assert_available_timeframe(name: str) -> str:
    """Ensure timeframe is in the LOT-003 available set."""
    key = normalize_timeframe(name)
    if key not in AVAILABLE_TIMEFRAMES:
        msg = (
            f"timeframe {key!r} is not in the available market-data set "
            f"{AVAILABLE_TIMEFRAMES}"
        )
        raise ValueError(msg)
    return key


def timeframe_delta(name: str) -> timedelta:
    """Return the bar duration for an available timeframe."""
    key = assert_available_timeframe(name)
    return _TIMEFRAME_DELTAS[key]


def timeframe_code(name: str) -> int:
    """Return the MT5 integer code for a timeframe name."""
    key = normalize_timeframe(name)
    return TIMEFRAME_NAME_TO_CODE[key]
