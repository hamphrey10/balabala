"""CFD-style position sizing (convention courante — vérifier chez le courtier)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from signal_desk.analysis import SignalResult

# USD P/L par unité de prix pour 1,00 lot (convention CFD fréquente)
USD_PER_PRICE_UNIT_PER_LOT: dict[str, float] = {
    "XAUUSD": 100.0,  # 100 oz
    "XAGUSD": 5000.0,  # 5 000 oz
}

CONTRACT_NOTE_FR = (
    "Convention retenue (CFD courant) : 1,00 lot XAUUSD = 100 oz, "
    "1,00 lot XAGUSD = 5 000 oz — votre courtier peut différer."
)


@dataclass(frozen=True)
class SizeRow:
    risk_usd: float
    lots: float
    risk_if_stop_usd: float
    reward_tp1_usd: float


@dataclass(frozen=True)
class SymbolSizing:
    symbol: str
    usd_per_price_001_lot: float
    usd_per_price_1_lot: float
    rows: list[SizeRow]


def _round_lots(raw: float) -> float:
    return max(0.01, math.floor(raw * 100 + 0.5) / 100)


def size_for_risk(symbol: str, dist_stop: float, dist_tp1: float, risk_usd: float) -> SizeRow:
    mult = USD_PER_PRICE_UNIT_PER_LOT[symbol]
    risk_per_lot = dist_stop * mult
    lots = _round_lots(risk_usd / risk_per_lot) if risk_per_lot > 0 else 0.01
    actual_risk = lots * dist_stop * mult
    reward = lots * dist_tp1 * mult
    return SizeRow(risk_usd=risk_usd, lots=lots, risk_if_stop_usd=round(actual_risk, 2), reward_tp1_usd=round(reward, 2))


def build_sizing(signal: SignalResult, budgets: tuple[float, ...] = (50.0, 100.0, 200.0)) -> SymbolSizing:
    sym = signal.symbol
    mult = USD_PER_PRICE_UNIT_PER_LOT[sym]
    rows = [
        size_for_risk(sym, signal.dist_entry_stop, signal.dist_entry_tp1, b)
        for b in budgets
    ]
    return SymbolSizing(
        symbol=sym,
        usd_per_price_001_lot=round(mult * 0.01, 4),
        usd_per_price_1_lot=mult,
        rows=rows,
    )
