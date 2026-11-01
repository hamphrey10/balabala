"""Structure-based swing setup on H4 candles — always emits a numeric plan."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

MIN_RR = 2.0
SWING_WINDOW = 2
BUFFER_PCT = 0.0015


class Bias(str, Enum):
    BULLISH = "haussier"
    BEARISH = "baissier"
    RANGE = "range"


class Side(str, Enum):
    BUY = "achat"
    SELL = "vente"


@dataclass
class SwingPoint:
    index: int
    price: float
    kind: str


@dataclass
class SignalResult:
    symbol: str
    bias: Bias
    side: Side
    last_price: float
    price_note_fr: str
    data_source: str
    signal_active: bool
    precondition_fr: str
    entry_zone_low: float
    entry_zone_high: float
    entry_mid: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    reward_risk: float
    dist_entry_stop: float
    dist_entry_tp1: float
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
    return sorted(highs + lows, key=lambda p: p.index)


def _recent_pivots(swings: list[SwingPoint], kind: str, count: int = 3) -> list[float]:
    return [s.price for s in swings if s.kind == kind][-count:]


def _detect_bias(swings: list[SwingPoint]) -> Bias:
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


def _range_bounds(swings: list[SwingPoint]) -> tuple[float, float]:
    highs = [s.price for s in swings if s.kind == "high"][-6:]
    lows = [s.price for s in swings if s.kind == "low"][-6:]
    if not highs or not lows:
        raise ValueError("Pas assez de pivots pour définir un plan.")
    return min(lows), max(highs)


def _pick_side(bias: Bias, last_price: float, range_low: float, range_high: float) -> Side:
    if bias == Bias.BULLISH:
        return Side.BUY
    if bias == Bias.BEARISH:
        return Side.SELL
    mid = (range_low + range_high) / 2
    return Side.BUY if last_price <= mid else Side.SELL


def _plan_long(
    entry_mid: float,
    swings: list[SwingPoint],
    atr: float,
    last_price: float,
    zone_half: float,
) -> tuple[float, float, float, float, float, float]:
    stop = entry_mid - max(atr * 0.35, entry_mid * BUFFER_PCT)
    risk = entry_mid - stop
    targets = _levels_above(entry_mid, swings, "high")
    if not targets:
        targets = [entry_mid + 2.5 * atr, entry_mid + 4.0 * atr]
    tp1 = targets[0]
    tp2 = targets[1] if len(targets) > 1 else tp1 + 1.5 * atr
    if risk > 0 and (tp1 - entry_mid) / risk < MIN_RR:
        tp1 = entry_mid + MIN_RR * risk
        tp2 = max(tp2, tp1 + 1.5 * atr)
    reward = tp1 - entry_mid
    rr = reward / risk if risk > 0 else 0.0
    z_low = entry_mid - zone_half
    z_high = entry_mid + zone_half
    return z_low, z_high, stop, tp1, tp2, rr


def _plan_short(
    entry_mid: float,
    swings: list[SwingPoint],
    atr: float,
    zone_half: float,
) -> tuple[float, float, float, float, float, float]:
    stop = entry_mid + max(atr * 0.35, entry_mid * BUFFER_PCT)
    risk = stop - entry_mid
    targets = _levels_below(entry_mid, swings, "low")
    if not targets:
        targets = [entry_mid - 2.5 * atr, entry_mid - 4.0 * atr]
    tp1 = targets[0]
    tp2 = targets[1] if len(targets) > 1 else tp1 - 1.5 * atr
    if risk > 0 and (entry_mid - tp1) / risk < MIN_RR:
        tp1 = entry_mid - MIN_RR * risk
        tp2 = min(tp2, tp1 - 1.5 * atr)
    reward = entry_mid - tp1
    rr = reward / risk if risk > 0 else 0.0
    z_low = entry_mid - zone_half
    z_high = entry_mid + zone_half
    return z_low, z_high, stop, tp1, tp2, rr


def _entry_level(
    side: Side,
    last_price: float,
    swings: list[SwingPoint],
    range_low: float,
    range_high: float,
) -> float:
    if side == Side.BUY:
        supports = _levels_below(last_price, swings, "low")
        return supports[0] if supports else range_low
    resistances = _levels_above(last_price, swings, "high")
    return resistances[0] if resistances else range_high


def _price_in_zone(last_price: float, z_low: float, z_high: float) -> bool:
    return z_low <= last_price <= z_high


def analyze(
    symbol: str,
    df: pd.DataFrame,
    last_price: float,
    price_note_fr: str,
    data_source: str,
) -> SignalResult:
    swings = _find_swings(df)
    bias = _detect_bias(swings)
    atr = _atr(df)
    range_low, range_high = _range_bounds(swings)
    side = _pick_side(bias, last_price, range_low, range_high)
    zone_half = max(atr * 0.15, last_price * 0.0008)
    entry_mid = _entry_level(side, last_price, swings, range_low, range_high)

    if side == Side.BUY:
        z_low, z_high, stop, tp1, tp2, rr = _plan_long(entry_mid, swings, atr, last_price, zone_half)
        dist_stop = entry_mid - stop
        dist_tp1 = tp1 - entry_mid
        commentary = (
            f"Plan achat : se placer à {entry_mid:.2f}, stop à {stop:.2f}, "
            f"objectifs à {tp1:.2f} et {tp2:.2f}."
        )
    else:
        z_low, z_high, stop, tp1, tp2, rr = _plan_short(entry_mid, swings, atr, zone_half)
        dist_stop = stop - entry_mid
        dist_tp1 = entry_mid - tp1
        commentary = (
            f"Plan vente : se placer à {entry_mid:.2f}, stop à {stop:.2f}, "
            f"objectifs à {tp1:.2f} et {tp2:.2f}."
        )

    rr = round(rr, 2)
    in_zone = _price_in_zone(last_price, z_low, z_high)
    bias_ok = bias != Bias.RANGE
    rr_ok = rr >= MIN_RR
    signal_active = bias_ok and rr_ok and in_zone

    if signal_active:
        precondition_fr = "Conditions réunies : vous pouvez placer l'ordre manuellement si le prix reste dans la zone."
    elif not bias_ok:
        precondition_fr = (
            "Attendre un biais H4 clair (série de plus hauts et plus bas) et un retest du niveau d'entrée "
            f"({z_low:.2f}–{z_high:.2f}) avant d'entrer."
        )
    elif not in_zone:
        precondition_fr = (
            f"Attendre que le prix revienne dans la zone d'entrée ({z_low:.2f}–{z_high:.2f}) "
            "avant de placer l'ordre ; ne pas chasser le marché."
        )
    else:
        precondition_fr = (
            f"Attendre un retest plus favorable ou un TP1 plus éloigné pour atteindre au moins {MIN_RR:.0f}× "
            f"gain/risque (actuellement {rr}×)."
        )

    return SignalResult(
        symbol=symbol,
        bias=bias,
        side=side,
        last_price=last_price,
        price_note_fr=price_note_fr,
        data_source=data_source,
        signal_active=signal_active,
        precondition_fr=precondition_fr,
        entry_zone_low=z_low,
        entry_zone_high=z_high,
        entry_mid=entry_mid,
        stop_loss=stop,
        take_profit_1=tp1,
        take_profit_2=tp2,
        reward_risk=rr,
        dist_entry_stop=abs(dist_stop),
        dist_entry_tp1=abs(dist_tp1),
        commentary=commentary,
    )
