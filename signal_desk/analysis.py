"""Structure-based swing setup on H4 candles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

MIN_RR = 2.0
SWING_WINDOW = 2
BUFFER_PCT = 0.0015  # ~0.15 % beyond invalidation level


class Bias(str, Enum):
    BULLISH = "haussier"
    BEARISH = "baissier"
    RANGE = "range"


@dataclass
class SwingPoint:
    index: int
    price: float
    kind: str  # "high" | "low"


@dataclass
class SignalResult:
    symbol: str
    bias: Bias
    last_price: float
    price_note_fr: str
    data_source: str
    signal_active: bool
    withhold_reason: str | None
    entry_zone_low: float | None
    entry_zone_high: float | None
    stop_loss: float | None
    take_profit_1: float | None
    take_profit_2: float | None
    reward_risk: float | None
    commentary: str


def _find_swings(df: pd.DataFrame, window: int = SWING_WINDOW) -> list[SwingPoint]:
    highs: list[SwingPoint] = []
    lows: list[SwingPoint] = []
    n = len(df)
    for i in range(window, n - window):
        h = float(df["high"].iloc[i])
        l = float(df["low"].iloc[i])
        seg_h = df["high"].iloc[i - window : i + window + 1]
        seg_l = df["low"].iloc[i - window : i + window + 1]
        if h >= seg_h.max():
            highs.append(SwingPoint(i, h, "high"))
        if l <= seg_l.min():
            lows.append(SwingPoint(i, l, "low"))
    merged = sorted(highs + lows, key=lambda p: p.index)
    return merged


def _recent_pivots(swings: list[SwingPoint], kind: str, count: int = 3) -> list[float]:
    return [s.price for s in swings if s.kind == kind][-count:]


def _detect_bias(df: pd.DataFrame, swings: list[SwingPoint]) -> Bias:
    highs = _recent_pivots(swings, "high", 3)
    lows = _recent_pivots(swings, "low", 3)
    if len(highs) < 2 or len(lows) < 2:
        return Bias.RANGE

    hh = highs[-1] > highs[-2]
    hl = lows[-1] > lows[-2]
    lh = highs[-1] < highs[-2]
    ll = lows[-1] < lows[-2]

    if hh and hl:
        return Bias.BULLISH
    if lh and ll:
        return Bias.BEARISH
    return Bias.RANGE


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    if len(df) < period + 1:
        return float(df["high"].sub(df["low"]).mean())
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return float(tr.tail(period).mean())


def _levels_above(price: float, swings: list[SwingPoint], kind: str) -> list[float]:
    return sorted({s.price for s in swings if s.kind == kind and s.price > price * 1.001})


def _levels_below(price: float, swings: list[SwingPoint], kind: str) -> list[float]:
    return sorted({s.price for s in swings if s.kind == kind and s.price < price * 0.999}, reverse=True)


def analyze(symbol: str, df: pd.DataFrame, last_price: float, price_note_fr: str, data_source: str) -> SignalResult:
    swings = _find_swings(df)
    bias = _detect_bias(df, swings)
    atr = _atr(df)

    base = SignalResult(
        symbol=symbol,
        bias=bias,
        last_price=last_price,
        price_note_fr=price_note_fr,
        data_source=data_source,
        signal_active=False,
        withhold_reason=None,
        entry_zone_low=None,
        entry_zone_high=None,
        stop_loss=None,
        take_profit_1=None,
        take_profit_2=None,
        reward_risk=None,
        commentary="",
    )

    if bias == Bias.RANGE:
        base.withhold_reason = (
            "Pas de signal : la structure H4 est en range, sans biais clair pour un retest."
        )
        base.commentary = "Attendre une série de plus hauts/bas cohérente avant de chercher une entrée."
        return base

    zone_half = max(atr * 0.15, last_price * 0.0008)

    if bias == Bias.BULLISH:
        supports = _levels_below(last_price, swings, "low")
        if not supports:
            base.withhold_reason = "Pas de signal : aucun support structurel identifiable sous le prix actuel."
            return base
        entry_mid = supports[0]
        entry_zone_low = entry_mid - zone_half
        entry_zone_high = entry_mid + zone_half
        stop_loss = entry_mid - max(atr * 0.35, entry_mid * BUFFER_PCT)
        risk = entry_mid - stop_loss
        targets = _levels_above(entry_mid, swings, "high")
        if not targets:
            targets = [entry_mid + 2.5 * atr, entry_mid + 4 * atr]
        tp1 = targets[0]
        tp2 = targets[1] if len(targets) > 1 else tp1 + 1.5 * atr
        reward = tp1 - entry_mid
        rr = reward / risk if risk > 0 else 0.0
        base.entry_zone_low = entry_zone_low
        base.entry_zone_high = entry_zone_high
        base.stop_loss = stop_loss
        base.take_profit_1 = tp1
        base.take_profit_2 = tp2
        base.reward_risk = round(rr, 2)
        base.commentary = "Idée longue : retest du dernier support H4 validé, stop sous invalidation."
        if rr < MIN_RR:
            base.withhold_reason = (
                f"Signal retenu : le rapport gain/risque vers TP1 ({rr:.2f}) est inférieur au minimum de 2."
            )
        else:
            base.signal_active = True
        return base

    # Bearish
    resistances = _levels_above(last_price, swings, "high")
    if not resistances:
        base.withhold_reason = "Pas de signal : aucune résistance structurelle identifiable au-dessus du prix actuel."
        return base
    entry_mid = resistances[0]
    entry_zone_low = entry_mid - zone_half
    entry_zone_high = entry_mid + zone_half
    stop_loss = entry_mid + max(atr * 0.35, entry_mid * BUFFER_PCT)
    risk = stop_loss - entry_mid
    targets = _levels_below(entry_mid, swings, "low")
    if not targets:
        targets = [entry_mid - 2.5 * atr, entry_mid - 4 * atr]
    tp1 = targets[0]
    tp2 = targets[1] if len(targets) > 1 else tp1 - 1.5 * atr
    reward = entry_mid - tp1
    rr = reward / risk if risk > 0 else 0.0
    base.entry_zone_low = entry_zone_low
    base.entry_zone_high = entry_zone_high
    base.stop_loss = stop_loss
    base.take_profit_1 = tp1
    base.take_profit_2 = tp2
    base.reward_risk = round(rr, 2)
    base.commentary = "Idée courte : retest de la dernière résistance H4, stop au-delà de l'invalidation."
    if rr < MIN_RR:
        base.withhold_reason = (
            f"Signal retenu : le rapport gain/risque vers TP1 ({rr:.2f}) est inférieur au minimum de 2."
        )
    else:
        base.signal_active = True
    return base
