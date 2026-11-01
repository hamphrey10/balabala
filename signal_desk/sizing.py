"""CFD-style position sizing (convention courante — vérifier chez le courtier)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from signal_desk.analysis import SignalResult

USD_PER_PRICE_UNIT_PER_LOT: dict[str, float] = {
    "XAUUSD": 100.0,
    "XAGUSD": 5000.0,
}

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
    slices: tuple[TpSlice, ...]
    risk_after_tp1_note_fr: str


@dataclass(frozen=True)
class SymbolSizing:
    symbol: str
    usd_per_price_001_lot: float
    usd_per_price_1_lot: float
    rows: list[SizeRow]
    ladder_100: LadderSizing | None = None


def _round_lots(raw: float) -> float:
    return max(0.01, math.floor(raw * 100 + 0.5) / 100)


def _split_lots(total: float, parts: int = 4) -> tuple[float, ...]:
    total = _round_lots(total)
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
    mult = USD_PER_PRICE_UNIT_PER_LOT[symbol]
    risk_per_lot = dist_stop * mult
    lots = _round_lots(risk_usd / risk_per_lot) if risk_per_lot > 0 else 0.01
    actual_risk = lots * dist_stop * mult
    reward = lots * dist_tp1 * mult
    return SizeRow(
        risk_usd=risk_usd,
        lots=lots,
        risk_if_stop_usd=round(actual_risk, 2),
        reward_tp1_usd=round(reward, 2),
    )


def _tp_distance(signal: SignalResult, tp_price: float) -> float:
    if signal.side.value == "achat":
        return abs(tp_price - signal.entry_mid)
    return abs(signal.entry_mid - tp_price)


def build_ladder_sizing(signal: SignalResult, risk_usd: float = 100.0) -> LadderSizing:
    mult = USD_PER_PRICE_UNIT_PER_LOT[signal.symbol]
    row = size_for_risk(
        signal.symbol, signal.dist_entry_stop, signal.dist_entry_tp1, risk_usd
    )
    lot_parts = _split_lots(row.lots)
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
    for i, (tp, lots, action) in enumerate(zip(tps, lot_parts, actions, strict=True), start=1):
        dist = _tp_distance(signal, tp)
        usd = round(lots * dist * mult, 2)
        slices.append(TpSlice(index=i, price=tp, lots=lots, usd_locked=usd, action_fr=action))

    remainder_risk = round(row.risk_if_stop_usd * (1.0 - LADDER_FRACTION), 2)
    note = (
        f"Après TP1 : ~{remainder_risk} USD encore exposés au stop initial tant que le stop n'est pas remonté ; "
        f"une fois le stop du reliquat (75 %) à l'entrée, risque ~0 USD hors spread/commission."
    )
    return LadderSizing(
        symbol=signal.symbol,
        risk_budget_usd=risk_usd,
        total_lots=row.lots,
        total_risk_at_stop_usd=row.risk_if_stop_usd,
        slices=tuple(slices),
        risk_after_tp1_note_fr=note,
    )


def build_sizing(signal: SignalResult, budgets: tuple[float, ...] = (50.0, 100.0, 200.0)) -> SymbolSizing:
    sym = signal.symbol
    mult = USD_PER_PRICE_UNIT_PER_LOT[sym]
    rows = [
        size_for_risk(sym, signal.dist_entry_stop, signal.dist_entry_tp1, b)
        for b in budgets
    ]
    ladder = build_ladder_sizing(signal, 100.0)
    return SymbolSizing(
        symbol=sym,
        usd_per_price_001_lot=round(mult * 0.01, 4),
        usd_per_price_1_lot=mult,
        rows=rows,
        ladder_100=ladder,
    )
