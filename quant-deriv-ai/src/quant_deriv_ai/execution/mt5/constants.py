"""Official MetaTrader5 account / timeframe constants.

Values match ENUM_ACCOUNT_TRADE_MODE and TIMEFRAME from the MQL5 Reference /
MetaTrader5 Python package. Prefer reading attributes from the imported
``MetaTrader5`` module when available; these fallbacks exist for unit tests
and hosts where the package cannot be imported (non-Windows).
"""

from __future__ import annotations

# ENUM_ACCOUNT_TRADE_MODE (Account Properties — MQL5 Reference)
ACCOUNT_TRADE_MODE_DEMO = 0
ACCOUNT_TRADE_MODE_CONTEST = 1
ACCOUNT_TRADE_MODE_REAL = 2

# TIMEFRAME enumeration (copy_rates_* — MQL5 Python docs)
TIMEFRAME_M1 = 1
TIMEFRAME_M2 = 2
TIMEFRAME_M3 = 3
TIMEFRAME_M4 = 4
TIMEFRAME_M5 = 5
TIMEFRAME_M6 = 6
TIMEFRAME_M10 = 10
TIMEFRAME_M12 = 12
TIMEFRAME_M15 = 15
TIMEFRAME_M20 = 20
TIMEFRAME_M30 = 30
TIMEFRAME_H1 = 16385
TIMEFRAME_H2 = 16386
TIMEFRAME_H3 = 16387
TIMEFRAME_H4 = 16388
TIMEFRAME_H6 = 16390
TIMEFRAME_H8 = 16392
TIMEFRAME_H12 = 16396
TIMEFRAME_D1 = 16408
TIMEFRAME_W1 = 32769
TIMEFRAME_MN1 = 49153

# COPY_TICKS flags
COPY_TICKS_ALL = -1
COPY_TICKS_INFO = 1
COPY_TICKS_TRADE = 2

TIMEFRAME_NAME_TO_CODE: dict[str, int] = {
    "M1": TIMEFRAME_M1,
    "M2": TIMEFRAME_M2,
    "M3": TIMEFRAME_M3,
    "M4": TIMEFRAME_M4,
    "M5": TIMEFRAME_M5,
    "M6": TIMEFRAME_M6,
    "M10": TIMEFRAME_M10,
    "M12": TIMEFRAME_M12,
    "M15": TIMEFRAME_M15,
    "M20": TIMEFRAME_M20,
    "M30": TIMEFRAME_M30,
    "H1": TIMEFRAME_H1,
    "H2": TIMEFRAME_H2,
    "H3": TIMEFRAME_H3,
    "H4": TIMEFRAME_H4,
    "H6": TIMEFRAME_H6,
    "H8": TIMEFRAME_H8,
    "H12": TIMEFRAME_H12,
    "D1": TIMEFRAME_D1,
    "W1": TIMEFRAME_W1,
    "MN1": TIMEFRAME_MN1,
}


def resolve_timeframe(name_or_code: str | int, mt5_module: object | None = None) -> int:
    """Resolve a timeframe name (e.g. ``H1``) or int using the live MT5 module when present."""
    if isinstance(name_or_code, int):
        return name_or_code
    key = name_or_code.strip().upper()
    attr = f"TIMEFRAME_{key}"
    if mt5_module is not None and hasattr(mt5_module, attr):
        return int(getattr(mt5_module, attr))
    if key in TIMEFRAME_NAME_TO_CODE:
        return TIMEFRAME_NAME_TO_CODE[key]
    msg = f"unknown timeframe: {name_or_code!r}"
    raise ValueError(msg)


def account_trade_mode_label(mode: int) -> str:
    """Human-readable label for ACCOUNT_TRADE_MODE."""
    mapping = {
        ACCOUNT_TRADE_MODE_DEMO: "demo",
        ACCOUNT_TRADE_MODE_CONTEST: "contest",
        ACCOUNT_TRADE_MODE_REAL: "real",
    }
    return mapping.get(mode, f"unknown({mode})")
