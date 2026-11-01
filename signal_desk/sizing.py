"""CFD-style position sizing (convention courante — vérifier chez le courtier)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from signal_desk.analysis import SignalResult

USD_PER_PRICE_UNIT_PER_LOT: dict[str, float] = {
    "XAUUSD": 100.0,
    "XAGUSD": 5000.0,
}

WEEK_RISK_USD = 20.0

CONTRACT_NOTE_FR = (
    "Convention retenue (CFD courant) : 1,00 lot XAUUSD = 100 oz, "
    "1,00 lot XAGUSD = 5 000 oz — votre courtier peut différer."
)

LADDER_FRACTION = 0.25


@dataclass(frozen=True)
class SizeRow:
    risk_usd: float
    lots: float
    risk_if_stop_usd: float
    reward_tp1_usd: float
    risk_note_fr: str | None = None


@dataclass(frozen=True)
class TpSlice:
    index: int
    price: float
    lots: float
    usd_locked: float
    action_fr: str


@dataclass(frozen=True)
class LadderSizing:
    symbol: str
    risk_budget_usd: float
    total_lots: float
    total_risk_at_stop_usd: float
    risk_budget_note_fr: str | None
    slices: tuple[TpSlice, ...]
    risk_after_tp1_note_fr: str
    ladder_total_usd: float


@dataclass(frozen=True)
class SymbolSizing:
    symbol: str
    usd_per_price_001_lot: float
    usd_per_price_1_lot: float
    rows: list[SizeRow]
    ladder_week: LadderSizing | None = None


def _round_lots_nearest(raw: float) -> float:
    return max(0.01, math.floor(raw * 100 + 0.5) / 100)


def _lots_for_budget(symbol: str, dist_stop: float, risk_usd: float) -> tuple[float, float, str | None]:
    """Floor to 0.01 lot so risk at stop stays at or under budget when possible."""
    mult = USD_PER_PRICE_UNIT_PER_LOT[symbol]
    risk_per_lot = dist_stop * mult
    if risk_per_lot <= 0:
        return 0.01, 0.01 * dist_stop * mult, "Distance stop nulle — vérifiez le plan."
    raw = risk_usd / risk_per_lot
    lots = math.floor(raw * 100) / 100
    if lots < 0.01:
        lots = 0.01
    actual = round(lots * dist_stop * mult, 2)
    note: str | None = None
    nearest = _round_lots_nearest(raw)
    nearest_risk = round(nearest * dist_stop * mult, 2)
    if nearest > lots and nearest_risk > risk_usd:
        note = (
            f"Arrondi au centième : 0,01 lot minimum → ~{actual} USD au stop "
            f"(budget visé {risk_usd:.0f} USD ; 0,02 lot risquerait ~{nearest_risk} USD)."
        )
    elif actual > risk_usd:
        note = (
            f"Risque réel au stop ~{actual} USD, au-dessus du budget {risk_usd:.0f} USD "
            f"(granularité 0,01 lot)."
        )
    return lots, actual, note


def _split_lots(total: float, parts: int = 4) -> tuple[float, ...]:
    total = max(0.01, round(total, 2))
    if total >= 0.04:
        base = math.floor((total / parts) * 100) / 100
        slices = [base] * parts
        remainder = round(total - base * parts, 2)
        i = 0
        while remainder >= 0.01 and i < parts:
            slices[i] = round(slices[i] + 0.01, 2)
            remainder = round(remainder - 0.01, 2)
            i += 1
        return tuple(slices)
    quarter = round(total / parts, 4)
    return (quarter, quarter, quarter, quarter)


def size_for_risk(symbol: str, dist_stop: float, dist_tp1: float, risk_usd: float) -> SizeRow:
    lots, actual_risk, note = _lots_for_budget(symbol, dist_stop, risk_usd)
    mult = USD_PER_PRICE_UNIT_PER_LOT[symbol]
    reward = lots * dist_tp1 * mult
    return SizeRow(
        risk_usd=risk_usd,
        lots=lots,
        risk_if_stop_usd=actual_risk,
        reward_tp1_usd=round(reward, 2),
        risk_note_fr=note,
    )


def _tp_distance(signal: SignalResult, tp_price: float) -> float:
    if signal.side.value == "achat":
        return abs(tp_price - signal.entry_mid)
    return abs(signal.entry_mid - tp_price)


def build_ladder_sizing(signal: SignalResult, risk_usd: float = WEEK_RISK_USD) -> LadderSizing:
    mult = USD_PER_PRICE_UNIT_PER_LOT[signal.symbol]
    lots, actual_risk, budget_note = _lots_for_budget(
        signal.symbol, signal.dist_entry_stop, risk_usd
    )
    lot_parts = _split_lots(lots)
    tps = (
        signal.take_profit_1,
        signal.take_profit_2,
        signal.take_profit_3,
        signal.take_profit_4,
    )
    actions = (
        "Clôturer 25 % ; stop du reliquat → entrée",
        "Clôturer 25 %",
        "Clôturer 25 %",
        "Clôturer 25 % (dernier quart)",
    )
    slices: list[TpSlice] = []
    ladder_total = 0.0
    for i, (tp, part_lots, action) in enumerate(zip(tps, lot_parts, actions, strict=True), start=1):
        dist = _tp_distance(signal, tp)
        usd = round(part_lots * dist * mult, 2)
        ladder_total += usd
        slices.append(TpSlice(index=i, price=tp, lots=part_lots, usd_locked=usd, action_fr=action))

    remainder_risk = round(actual_risk * (1.0 - LADDER_FRACTION), 2)
    note = (
        f"Avant TP1 : ~{actual_risk} USD au stop initial sur 100 % de la ligne. "
        f"Après TP1 (25 % sorti) : ~{remainder_risk} USD tant que le stop n'est pas à l'entrée ; "
        f"puis ~0 USD sur le reliquat hors spread."
    )
    return LadderSizing(
        symbol=signal.symbol,
        risk_budget_usd=risk_usd,
        total_lots=lots,
        total_risk_at_stop_usd=actual_risk,
        risk_budget_note_fr=budget_note,
        slices=tuple(slices),
        risk_after_tp1_note_fr=note,
        ladder_total_usd=round(ladder_total, 2),
    )


def build_sizing(
    signal: SignalResult, budgets: tuple[float, ...] = (20.0, 50.0, 100.0)
) -> SymbolSizing:
    sym = signal.symbol
    mult = USD_PER_PRICE_UNIT_PER_LOT[sym]
    rows = [
        size_for_risk(sym, signal.dist_entry_stop, signal.dist_entry_tp1, b)
        for b in budgets
    ]
    ladder = build_ladder_sizing(signal, WEEK_RISK_USD)
    return SymbolSizing(
        symbol=sym,
        usd_per_price_001_lot=round(mult * 0.01, 4),
        usd_per_price_1_lot=mult,
        rows=rows,
        ladder_week=ladder,
    )
