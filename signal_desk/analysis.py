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
    take_profit_3: float
    take_profit_4: float
    reward_risk: float
    dist_entry_stop: float
    dist_entry_tp1: float
    ladder_note_fr: str
    commentary: str
    order_type_fr: str
    order_instruction_fr: str
    order_trigger_price: float


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


def _four_tps_long(
    entry_mid: float, stop: float, swings: list[SwingPoint], atr: float
) -> tuple[float, float, float, float, float]:
    risk = entry_mid - stop
    if risk <= 0:
        risk = entry_mid * BUFFER_PCT
    tp1 = entry_mid + risk
    highs = _levels_above(entry_mid, swings, "high")
    tp4 = max(highs) if highs else entry_mid + 4.0 * atr
    if tp4 < tp1 + risk * 0.25:
        tp4 = entry_mid + max(MIN_RR * risk, 3.0 * risk)
    span = tp4 - tp1
    tp2 = tp1 + span / 3.0
    tp3 = tp1 + 2.0 * span / 3.0
    rr = (tp4 - entry_mid) / risk
    return tp1, tp2, tp3, tp4, rr


def _four_tps_short(
    entry_mid: float, stop: float, swings: list[SwingPoint], atr: float
) -> tuple[float, float, float, float, float]:
    risk = stop - entry_mid
    if risk <= 0:
        risk = entry_mid * BUFFER_PCT
    tp1 = entry_mid - risk
    lows = _levels_below(entry_mid, swings, "low")
    tp4 = min(lows) if lows else entry_mid - 4.0 * atr
    if tp4 > tp1 - risk * 0.25:
        tp4 = entry_mid - max(MIN_RR * risk, 3.0 * risk)
    span = tp1 - tp4
    tp2 = tp1 - span / 3.0
    tp3 = tp1 - 2.0 * span / 3.0
    rr = (entry_mid - tp4) / risk
    return tp1, tp2, tp3, tp4, rr


def _plan_long(
    entry_mid: float,
    swings: list[SwingPoint],
    atr: float,
    zone_half: float,
) -> tuple[float, float, float, float, float, float, float, float, float]:
    stop = entry_mid - max(atr * 0.35, entry_mid * BUFFER_PCT)
    tp1, tp2, tp3, tp4, rr = _four_tps_long(entry_mid, stop, swings, atr)
    z_low = entry_mid - zone_half
    z_high = entry_mid + zone_half
    return z_low, z_high, stop, tp1, tp2, tp3, tp4, rr


def _plan_short(
    entry_mid: float,
    swings: list[SwingPoint],
    atr: float,
    zone_half: float,
) -> tuple[float, float, float, float, float, float, float, float, float]:
    stop = entry_mid + max(atr * 0.35, entry_mid * BUFFER_PCT)
    tp1, tp2, tp3, tp4, rr = _four_tps_short(entry_mid, stop, swings, atr)
    z_low = entry_mid - zone_half
    z_high = entry_mid + zone_half
    return z_low, z_high, stop, tp1, tp2, tp3, tp4, rr


LADDER_NOTE_FR = (
    "Sortie en 4 tranches de 25 % : à TP1 (~1R), clôturer 25 % et placer le stop du reliquat au prix d'entrée "
    "(hors spread) ; TP2–TP4, 25 % chacun. Tant que TP1 n'est pas touché, le risque complet au stop initial reste entier."
)


def _recent_low_below(df: pd.DataFrame, last_price: float, lookback: int = 30) -> float | None:
    tail = df.tail(lookback)
    below = tail[tail["low"] < last_price * 0.999]["low"]
    if below.empty:
        return None
    return float(below.min())


def _recent_high_above(df: pd.DataFrame, last_price: float, lookback: int = 30) -> float | None:
    tail = df.tail(lookback)
    above = tail[tail["high"] > last_price * 1.001]["high"]
    if above.empty:
        return None
    return float(above.max())


def _resolve_side_and_entry(
    side: Side,
    last_price: float,
    swings: list[SwingPoint],
    range_low: float,
    range_high: float,
    df: pd.DataFrame,
) -> tuple[Side, float, str]:
    """Pick entry on the correct side of price for retest logic (no buy limit above market)."""
    note = ""
    if side == Side.BUY:
        supports = _levels_below(last_price, swings, "low")
        if supports:
            return Side.BUY, supports[0], note
        if range_low > last_price * 1.001:
            note = (
                "Ancien support au-dessus du cours : bascule en retest vente (support devenu résistance)."
            )
            return Side.SELL, range_low, note
        alt = _recent_low_below(df, last_price)
        if alt is not None:
            return Side.BUY, alt, note
        if range_high > last_price:
            note = "Retest résistance après cassure : vente sur remontée."
            return Side.SELL, range_high, note
        return Side.BUY, last_price * 0.998, note

    resistances = _levels_above(last_price, swings, "high")
    if resistances:
        return Side.SELL, resistances[0], note
    if range_high < last_price * 0.999:
        note = "Ancienne résistance sous le cours : bascule en retest achat (résistance devenue support)."
        return Side.BUY, range_high, note
    alt = _recent_high_above(df, last_price)
    if alt is not None:
        return Side.SELL, alt, note
    return Side.SELL, last_price * 1.002, note


def _derive_order(side: Side, last_price: float, z_low: float, z_high: float, entry_mid: float) -> tuple[str, str, float]:
    tick = max(last_price * 0.00005, 0.01)
    if side == Side.BUY:
        if z_high < last_price - tick:
            return (
                "Buy limit",
                f"Poser maintenant un buy limit à {entry_mid:.2f} (zone sous le cours {last_price:.2f}) ; "
                "exécution si le prix redescend en retest.",
                entry_mid,
            )
        if z_low > last_price + tick:
            raise ValueError("Plan achat incohérent : zone au-dessus du cours.")
        return (
            "Buy limit",
            f"Attendre : cours dans la zone — buy limit au bas ({z_low:.2f}) ou validation manuelle avant entrée.",
            z_low,
        )

    if z_low > last_price + tick:
        return (
            "Sell limit",
            f"Poser maintenant un sell limit à {entry_mid:.2f} (zone au-dessus du cours {last_price:.2f}) ; "
            "exécution au retest si le prix remonte.",
            entry_mid,
        )
    if z_high < last_price - tick:
        raise ValueError("Plan vente incohérent : zone sous le cours sans cassure validée.")
    return (
        "Sell limit",
        f"Attendre : cours dans la zone — sell limit au haut ({z_high:.2f}) ou validation manuelle.",
        z_high,
    )


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
    side_hint = _pick_side(bias, last_price, range_low, range_high)
    zone_half = max(atr * 0.15, last_price * 0.0008)
    side, entry_mid, flip_note = _resolve_side_and_entry(
        side_hint, last_price, swings, range_low, range_high, df
    )

    if side == Side.BUY:
        z_low, z_high, stop, tp1, tp2, tp3, tp4, rr = _plan_long(
            entry_mid, swings, atr, zone_half
        )
        dist_stop = entry_mid - stop
        dist_tp1 = tp1 - entry_mid
        commentary = (
            f"Plan achat : entrée {entry_mid:.2f}, stop {stop:.2f}, "
            f"échelle TP {tp1:.2f} / {tp2:.2f} / {tp3:.2f} / {tp4:.2f}."
        )
        if flip_note:
            commentary = f"{flip_note} {commentary}"
    else:
        z_low, z_high, stop, tp1, tp2, tp3, tp4, rr = _plan_short(
            entry_mid, swings, atr, zone_half
        )
        dist_stop = stop - entry_mid
        dist_tp1 = entry_mid - tp1
        commentary = (
            f"Plan vente : entrée {entry_mid:.2f}, stop {stop:.2f}, "
            f"échelle TP {tp1:.2f} / {tp2:.2f} / {tp3:.2f} / {tp4:.2f}."
        )
        if flip_note:
            commentary = f"{flip_note} {commentary}"

    order_type_fr, order_instruction_fr, order_trigger = _derive_order(
        side, last_price, z_low, z_high, entry_mid
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
        take_profit_3=tp3,
        take_profit_4=tp4,
        reward_risk=rr,
        dist_entry_stop=abs(dist_stop),
        dist_entry_tp1=abs(dist_tp1),
        ladder_note_fr=LADDER_NOTE_FR,
        commentary=commentary,
        order_type_fr=order_type_fr,
        order_instruction_fr=order_instruction_fr,
        order_trigger_price=order_trigger,
    )
