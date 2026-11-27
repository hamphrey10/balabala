"""UTC normalization and typed DataFrame contracts for market series."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from quant_deriv_ai.execution.mt5.models import Candle, TickData
from quant_deriv_ai.market_data.models import SeriesKind

CANDLE_COLUMNS: tuple[str, ...] = (
    "symbol",
    "timeframe",
    "time",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
    "is_reconstructed",
    "reconstruction_method",
)

TICK_COLUMNS: tuple[str, ...] = (
    "symbol",
    "time",
    "bid",
    "ask",
    "last",
    "volume",
    "flags",
    "is_reconstructed",
    "reconstruction_method",
)


def ensure_utc(value: datetime) -> datetime:
    """Force a datetime to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def candles_to_frame(candles: list[Candle]) -> pd.DataFrame:
    """Convert Candle models to a normalized UTC DataFrame."""
    if not candles:
        return empty_candles_frame()
    rows: list[dict[str, Any]] = []
    for c in candles:
        rows.append(
            {
                "symbol": c.symbol,
                "timeframe": c.timeframe.upper(),
                "time": ensure_utc(c.time),
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "tick_volume": int(c.tick_volume),
                "spread": int(c.spread),
                "real_volume": int(c.real_volume),
                "is_reconstructed": False,
                "reconstruction_method": "none",
            }
        )
    frame = pd.DataFrame(rows, columns=list(CANDLE_COLUMNS))
    return normalize_frame(frame, SeriesKind.CANDLES)


def ticks_to_frame(ticks: list[TickData]) -> pd.DataFrame:
    """Convert TickData models to a normalized UTC DataFrame."""
    if not ticks:
        return empty_ticks_frame()
    rows: list[dict[str, Any]] = []
    for t in ticks:
        rows.append(
            {
                "symbol": t.symbol,
                "time": ensure_utc(t.time),
                "bid": float(t.bid),
                "ask": float(t.ask),
                "last": float(t.last),
                "volume": float(t.volume),
                "flags": int(t.flags),
                "is_reconstructed": False,
                "reconstruction_method": "none",
            }
        )
    frame = pd.DataFrame(rows, columns=list(TICK_COLUMNS))
    return normalize_frame(frame, SeriesKind.TICKS)


def empty_candles_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(CANDLE_COLUMNS))


def empty_ticks_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(TICK_COLUMNS))


def normalize_frame(frame: pd.DataFrame, kind: SeriesKind) -> pd.DataFrame:
    """Ensure column set, UTC timestamps, sorted unique order, and flags."""
    expected = CANDLE_COLUMNS if kind is SeriesKind.CANDLES else TICK_COLUMNS
    out = frame.copy()
    for col in expected:
        if col not in out.columns:
            if col == "is_reconstructed":
                out[col] = False
            elif col == "reconstruction_method":
                out[col] = "none"
            else:
                out[col] = pd.NA
    out = out.loc[:, list(expected)]
    if out.empty:
        return out

    out["time"] = pd.to_datetime(out["time"], utc=True)
    if "is_reconstructed" in out.columns:
        out["is_reconstructed"] = out["is_reconstructed"].fillna(False).astype(bool)
    if "reconstruction_method" in out.columns:
        out["reconstruction_method"] = (
            out["reconstruction_method"].fillna("none").astype(str)
        )

    if kind is SeriesKind.CANDLES:
        out["timeframe"] = out["timeframe"].astype(str).str.upper()
        for col in ("open", "high", "low", "close"):
            out[col] = pd.to_numeric(out[col], errors="coerce")
        for col in ("tick_volume", "spread", "real_volume"):
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype("int64")
    else:
        for col in ("bid", "ask", "last", "volume"):
            out[col] = pd.to_numeric(out[col], errors="coerce")
        out["flags"] = pd.to_numeric(out["flags"], errors="coerce").fillna(0).astype("int64")

    out = out.sort_values("time", kind="mergesort").reset_index(drop=True)
    return out


def merge_incremental(existing: pd.DataFrame, new: pd.DataFrame, kind: SeriesKind) -> pd.DataFrame:
    """Append new rows, drop exact time duplicates (keep last), keep UTC order."""
    if existing.empty:
        return normalize_frame(new, kind)
    if new.empty:
        return normalize_frame(existing, kind)
    combined = pd.concat([existing, new], ignore_index=True)
    combined = normalize_frame(combined, kind)
    # Deduplicate on time (+ timeframe for candles) keeping the newest write.
    subset = ["time", "timeframe"] if kind is SeriesKind.CANDLES else ["time"]
    combined = combined.drop_duplicates(subset=subset, keep="last").reset_index(drop=True)
    return combined
