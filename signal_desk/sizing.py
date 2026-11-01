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
MIN_LOT = 0.01
LADDER_MIN_TOTAL_LOTS = 0.04
LADDER_FRACTION = 0.25

CONTRACT_NOTE_FR = (
    "Convention retenue (CFD courant) : 1,00 lot XAUUSD = 100 oz, "
    "1,00 lot XAGUSD = 5 000 oz — clôture partielle minimum 0,01 lot chez la plupart des courtiers."
)


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
class ExecutableMicroPlan:
    """Phase 20 USD : une ligne 0,01 lot, un seul TP (~1R), clôture totale."""

    symbol: str
    risk_budget_usd: float
    lots: float
    stop_risk_usd: float
    take_profit_price: float
    take_profit_usd: float
    order_summary_fr: str
    ladder_unavailable_fr: str
    risk_note_fr: str | None


@dataclass(frozen=True)
class SymbolSizing:
    symbol: str
    usd_per_price_001_lot: float
    usd_per_price_1_lot: float
    rows: list[SizeRow]
    week_micro: ExecutableMicroPlan
    ladder_at_min_size: LadderSizing | None


def _lots_for_budget(symbol: str, dist_stop: float, risk_usd: float) -> tuple[float, float, str | None]:
    mult = USD_PER_PRICE_UNIT_PER_LOT[symbol]
    risk_per_lot = dist_stop * mult
    if risk_per_lot <= 0:
        return MIN_LOT, MIN_LOT * dist_stop * mult, "Distance stop nulle — vérifiez le plan."
    raw = risk_usd / risk_per_lot
    lots = math.floor(raw * 100) / 100
    if lots < MIN_LOT:
        lots = MIN_LOT
    actual = round(lots * dist_stop * mult, 2)
    note: str | None = None
    risk_002 = round(0.02 * dist_stop * mult, 2)
    if lots == MIN_LOT and risk_002 > risk_usd:
        note = (
            f"Phase {risk_usd:.0f} USD : seulement 0,01 lot exécutable (~{actual} USD au stop). "
            f"0,02 lot → ~{risk_002} USD (> budget)."
        )
    elif actual > risk_usd:
        note = f"Risque réel ~{actual} USD (> budget {risk_usd:.0f} USD)."
    return lots, actual, note


def _split_lots(total: float, parts: int = 4) -> tuple[float, ...]:
    total = max(MIN_LOT, round(total, 2))
    if total < LADDER_MIN_TOTAL_LOTS:
        raise ValueError("Échelle 4×0,01 lot impossible sous 0,04 lot total.")
    base = math.floor((total / parts) * 100) / 100
    slices = [base] * parts
    remainder = round(total - base * parts, 2)
    i = 0
    while remainder >= 0.01 and i < parts:
        slices[i] = round(slices[i] + 0.01, 2)
        remainder = round(remainder - 0.01, 2)
        i += 1
    return tuple(slices)


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


def build_micro_plan(signal: SignalResult, risk_usd: float = WEEK_RISK_USD) -> ExecutableMicroPlan:
    mult = USD_PER_PRICE_UNIT_PER_LOT[signal.symbol]
    lots, stop_risk, note = _lots_for_budget(signal.symbol, signal.dist_entry_stop, risk_usd)
    lots = MIN_LOT if lots < MIN_LOT else lots
    if lots > MIN_LOT and lots < LADDER_MIN_TOTAL_LOTS:
        lots = MIN_LOT
        stop_risk = round(MIN_LOT * signal.dist_entry_stop * mult, 2)
    tp = signal.take_profit_1
    dist = signal.dist_entry_tp1
    tp_usd = round(lots * dist * mult, 2)
    risk_ladder = round(LADDER_MIN_TOTAL_LOTS * signal.dist_entry_stop * mult, 2)
    blocked = (
        f"L’échelle 4 TP (4× clôture 0,01 lot) exige 0,04 lot minimum "
        f"(~{risk_ladder} USD au stop ici) — indisponible en phase {risk_usd:.0f} USD."
    )
    order = (
        f"{signal.order_type_fr} à {signal.entry_mid:.2f}, 0,01 lot, "
        f"stop {signal.stop_loss:.2f}, take profit unique {tp:.2f} (~1R, clôture totale)."
    )
    return ExecutableMicroPlan(
        symbol=signal.symbol,
        risk_budget_usd=risk_usd,
        lots=lots,
        stop_risk_usd=stop_risk,
        take_profit_price=tp,
        take_profit_usd=tp_usd,
        order_summary_fr=order,
        ladder_unavailable_fr=blocked,
        risk_note_fr=note,
    )


def build_ladder_sizing(signal: SignalResult, total_lots: float, risk_usd: float) -> LadderSizing:
    mult = USD_PER_PRICE_UNIT_PER_LOT[signal.symbol]
    lots = max(LADDER_MIN_TOTAL_LOTS, round(total_lots, 2))
    actual_risk = round(lots * signal.dist_entry_stop * mult, 2)
    lot_parts = _split_lots(lots)
    tps = (
        signal.take_profit_1,
        signal.take_profit_2,
        signal.take_profit_3,
        signal.take_profit_4,
    )
    actions = (
        "Clôturer 0,01 lot ; stop reliquat → entrée",
        "Clôturer 0,01 lot",
        "Clôturer 0,01 lot",
        "Clôturer 0,01 lot (dernier quart)",
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
        f"Avant TP1 : ~{actual_risk} USD au stop. Après TP1 (0,01 lot sorti) : "
        f"~{remainder_risk} USD tant que le stop n'est pas à l'entrée ; puis ~0 USD sur le reliquat."
    )
    return LadderSizing(
        symbol=signal.symbol,
        risk_budget_usd=risk_usd,
        total_lots=lots,
        total_risk_at_stop_usd=actual_risk,
        risk_budget_note_fr=None,
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
    micro = build_micro_plan(signal, WEEK_RISK_USD)
    ladder: LadderSizing | None = None
    try:
        ladder = build_ladder_sizing(signal, LADDER_MIN_TOTAL_LOTS, WEEK_RISK_USD)
    except ValueError:
        ladder = None
    return SymbolSizing(
        symbol=sym,
        usd_per_price_001_lot=round(mult * 0.01, 4),
        usd_per_price_1_lot=mult,
        rows=rows,
        week_micro=micro,
        ladder_at_min_size=ladder,
    )
