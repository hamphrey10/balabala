"""Swing points, support/resistance, and market structure (causal)."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from quant_deriv_ai.technical.models import (
    StructureBias,
    StructureLevel,
    SwingKind,
    SwingPoint,
)


def detect_swings(
    high: pd.Series,
    low: pd.Series,
    *,
    left: int = 2,
    right: int = 2,
    times: pd.Series | None = None,
) -> list[SwingPoint]:
    """Fractal swing highs/lows using only confirmed pivots.

    A pivot at index ``i`` is confirmed only when ``i + right`` bars exist,
    so the label is available at bar ``i + right`` (no look-ahead into unconfirmed
    future when used with a confirmation lag in the engine).
    """
    if left < 1 or right < 1:
        msg = "left and right must be >= 1"
        raise ValueError(msg)
    highs = high.astype(float).to_numpy()
    lows = low.astype(float).to_numpy()
    n = len(highs)
    swings: list[SwingPoint] = []
    for i in range(left, n - right):
        window_h = highs[i - left : i + right + 1]
        window_l = lows[i - left : i + right + 1]
        is_high = highs[i] == np.max(window_h) and np.sum(window_h == highs[i]) == 1
        is_low = lows[i] == np.min(window_l) and np.sum(window_l == lows[i]) == 1
        t: datetime | None = None
        if times is not None and i < len(times):
            raw = times.iloc[i]
            t = pd.Timestamp(raw).to_pydatetime() if pd.notna(raw) else None
        if is_high:
            swings.append(
                SwingPoint(kind=SwingKind.HIGH, index=i, time=t, price=float(highs[i]))
            )
        if is_low:
            swings.append(
                SwingPoint(kind=SwingKind.LOW, index=i, time=t, price=float(lows[i]))
            )
    return swings


def support_resistance_from_swings(
    swings: list[SwingPoint],
    *,
    tol_pct: float = 0.001,
    max_levels: int = 8,
) -> list[StructureLevel]:
    """Cluster swing prices into support (lows) / resistance (highs)."""
    if not swings:
        return []
    highs = [s for s in swings if s.kind is SwingKind.HIGH]
    lows = [s for s in swings if s.kind is SwingKind.LOW]
    levels: list[StructureLevel] = []
    levels.extend(_cluster(highs, kind="resistance", tol_pct=tol_pct))
    levels.extend(_cluster(lows, kind="support", tol_pct=tol_pct))
    # Prefer levels with more touches, then nearer mid of set.
    levels.sort(key=lambda x: (-x.touches, x.price))
    return levels[:max_levels]


def _cluster(
    points: list[SwingPoint],
    *,
    kind: str,
    tol_pct: float,
) -> list[StructureLevel]:
    if not points:
        return []
    prices = sorted(p.price for p in points)
    clusters: list[list[float]] = [[prices[0]]]
    for price in prices[1:]:
        ref = float(np.mean(clusters[-1]))
        if ref == 0:
            if abs(price - ref) <= tol_pct:
                clusters[-1].append(price)
            else:
                clusters.append([price])
        elif abs(price - ref) / abs(ref) <= tol_pct:
            clusters[-1].append(price)
        else:
            clusters.append([price])
    return [
        StructureLevel(
            kind=kind,
            price=float(np.mean(c)),
            touches=len(c),
            source="swing",
        )
        for c in clusters
    ]


def structure_bias_from_swings(swings: list[SwingPoint]) -> StructureBias:
    """Higher-highs / higher-lows vs lower-highs / lower-lows using last swings."""
    highs = [s.price for s in swings if s.kind is SwingKind.HIGH]
    lows = [s.price for s in swings if s.kind is SwingKind.LOW]
    if len(highs) < 2 or len(lows) < 2:
        return StructureBias.UNKNOWN
    hh = highs[-1] > highs[-2]
    hl = lows[-1] > lows[-2]
    lh = highs[-1] < highs[-2]
    ll = lows[-1] < lows[-2]
    if hh and hl:
        return StructureBias.BULLISH
    if lh and ll:
        return StructureBias.BEARISH
    return StructureBias.RANGE
