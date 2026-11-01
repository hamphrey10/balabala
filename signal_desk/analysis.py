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
    if tp4 <= entry_mid:
        tp4 = entry_mid + 4.0 * atr
    span = max(tp4 - tp1, 0.0)
    if span <= 0:
        tp2 = tp3 = tp4
    else:
        tp2 = tp1 + span / 3.0
        tp3 = tp1 + 2.0 * span / 3.0
    rr = (tp4 - entry_mid) / risk if risk > 0 else 0.0
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
    if tp4 >= entry_mid:
        tp4 = entry_mid - 4.0 * atr
    span = max(tp1 - tp4, 0.0)
    if span <= 0:
        tp2 = tp3 = tp4
    else:
        tp2 = tp1 - span / 3.0
        tp3 = tp1 - 2.0 * span / 3.0
    rr = (entry_mid - tp4) / risk if risk > 0 else 0.0
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


def _zone_fully_below(last_price: float, z_low: float, z_high: float) -> bool:
    tick = max(last_price * 0.00005, 0.01)
    return z_high < last_price - tick


def _zone_fully_above(last_price: float, z_low: float, z_high: float) -> bool:
    tick = max(last_price * 0.00005, 0.01)
    return z_low > last_price + tick


def _derive_order(side: Side, last_price: float, z_low: float, z_high: float, entry_mid: float) -> tuple[str, str, float]:
    if side == Side.BUY:
        if _zone_fully_below(last_price, z_low, z_high):
            return (
                "Buy limit",
                f"Poser maintenant un buy limit à {entry_mid:.2f} (zone sous le cours {last_price:.2f}) ; "
                "exécution si le prix redescend. Pas d'ordre au marché tant que le cours est hors zone.",
                entry_mid,
            )
        if _zone_fully_above(last_price, z_low, z_high):
            raise ValueError("Plan achat incohérent : zone au-dessus du cours.")
        return (
            "Buy limit",
            f"Cours dans la zone : entrée manuelle possible ; pas d'achat au marché sans validation du retest.",
            entry_mid,
        )

    if _zone_fully_above(last_price, z_low, z_high):
        return (
            "Sell limit",
            f"Poser maintenant un sell limit à {entry_mid:.2f} (zone au-dessus du cours {last_price:.2f}) ; "
            "exécution si le prix remonte. Pas d'ordre au marché tant que le cours est hors zone.",
            entry_mid,
        )
    if _zone_fully_below(last_price, z_low, z_high):
        raise ValueError("Plan vente incohérent : zone sous le cours sans cassure validée.")
    return (
        "Sell limit",
        f"Cours dans la zone : entrée manuelle possible ; pas de vente au marché sans validation du retest.",
        entry_mid,
    )


def _build_precondition(
    *,
    signal_active: bool,
    bias_ok: bool,
    rr_ok: bool,
    in_zone: bool,
    rr: float,
    z_low: float,
    z_high: float,
    order_type_fr: str,
    order_trigger: float,
    pending_outside_zone: bool,
) -> str:
    if signal_active:
        return (
            "Signal actif : retest en zone et R/R structurel ≥ 2× — exécution manuelle possible "
            "(éviter le marché si le spread est défavorable)."
        )
    parts: list[str] = []
    if pending_outside_zone:
        parts.append(
            f"{order_type_fr} posable maintenant à {order_trigger:.2f} : exécution uniquement si le prix "
            f"revient dans {z_low:.2f}–{z_high:.2f} ; pas d'ordre au marché hors zone."
        )
    elif not in_zone:
        parts.append(
            f"Cours hors zone {z_low:.2f}–{z_high:.2f} : pas d'ordre au marché ; attendre le retest."
        )
    if not bias_ok:
        parts.append("Signal retenu : biais H4 non confirmé (range ou structure mixte).")
    if not rr_ok:
        parts.append(
            f"Signal retenu : l'objectif structurel TP4 ne paye que {rr}× le risque (minimum {MIN_RR:.0f}×)."
        )
    return " ".join(parts)


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
    pending_outside = (side == Side.BUY and _zone_fully_below(last_price, z_low, z_high)) or (
        side == Side.SELL and _zone_fully_above(last_price, z_low, z_high)
    )
    signal_active = bias_ok and rr_ok and in_zone
    precondition_fr = _build_precondition(
        signal_active=signal_active,
        bias_ok=bias_ok,
        rr_ok=rr_ok,
        in_zone=in_zone,
        rr=rr,
        z_low=z_low,
        z_high=z_high,
        order_type_fr=order_type_fr,
        order_trigger=order_trigger,
        pending_outside_zone=pending_outside,
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
