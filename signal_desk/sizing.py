"""CFD-style position sizing (convention courante — vérifier chez le courtier)."""

from __future__ import annotations

from dataclasses import dataclass

from signal_desk.analysis import SignalResult

USD_PER_PRICE_UNIT_PER_LOT: dict[str, float] = {
    "XAUUSD": 100.0,
    "XAGUSD": 5000.0,
}

WEEK_RISK_USD = 20.0
PREFERRED_SLICE = 0.004
SLICES = 4
MIN_SLICE = 0.001

BROKER_MILLI_NOTE_FR = (
    "Cette échelle 4 TP n’est exécutable que si le minimum lot et la clôture partielle "
    "du courtier sont 0,001 ou plus fin ; si le minimum est 0,01, cette échelle ne peut pas être placée."
)

CONTRACT_NOTE_FR = (
    "Convention retenue (CFD courant) : 1,00 lot XAUUSD = 100 oz, "
    "1,00 lot XAGUSD = 5 000 oz — pas de promesse de gain."
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
    slice_lots: float
    total_lots: float
    total_risk_at_stop_usd: float
    risk_budget_note_fr: str | None
    order_summary_fr: str
    broker_note_fr: str
    slices: tuple[TpSlice, ...]
    risk_after_tp1_note_fr: str
    ladder_total_usd: float


@dataclass(frozen=True)
class SymbolSizing:
    symbol: str
    usd_per_price_001_lot: float
    usd_per_price_1_lot: float
    rows: list[SizeRow]
    week_ladder: LadderSizing


def _risk_usd(symbol: str, dist_stop: float, lots: float) -> float:
    return lots * dist_stop * USD_PER_PRICE_UNIT_PER_LOT[symbol]


def _pick_four_slices(symbol: str, dist_stop: float, budget: float) -> tuple[float, float, float, str | None]:
    """Return (slice_lot, total_lots, stop_risk_usd, note)."""
    slice_lot = PREFERRED_SLICE
    note: str | None = None
    while slice_lot >= MIN_SLICE - 1e-9:
        total = round(slice_lot * SLICES, 3)
        risk = round(_risk_usd(symbol, dist_stop, total), 2)
        if risk <= budget + 0.001:
            if slice_lot < PREFERRED_SLICE:
                note = (
                    f"0,004×4 dépassait {budget:.0f} USD au stop ; tranches abaissées à {slice_lot:.3f} lot "
                    f"(total {total:.3f} lot, ~{risk} USD)."
                )
            return slice_lot, total, risk, note
        slice_lot = round(slice_lot - 0.001, 3)
    total = round(MIN_SLICE * SLICES, 3)
    risk = round(_risk_usd(symbol, dist_stop, total), 2)
    note = f"Même à 4×0,001 lot, risque ~{risk} USD — vérifier le budget {budget:.0f} USD."
    return MIN_SLICE, total, risk, note


def size_for_risk(symbol: str, dist_stop: float, dist_tp1: float, risk_usd: float) -> SizeRow:
    _, total, actual_risk, note = _pick_four_slices(symbol, dist_stop, risk_usd)
    mult = USD_PER_PRICE_UNIT_PER_LOT[symbol]
    reward = total * dist_tp1 * mult
    return SizeRow(
        risk_usd=risk_usd,
        lots=total,
        risk_if_stop_usd=actual_risk,
        reward_tp1_usd=round(reward, 2),
        risk_note_fr=note,
    )


def _tp_distance(signal: SignalResult, tp_price: float) -> float:
    if signal.side.value == "achat":
        return abs(tp_price - signal.entry_mid)
    return abs(signal.entry_mid - tp_price)


def build_week_ladder(signal: SignalResult, risk_usd: float = WEEK_RISK_USD) -> LadderSizing:
    mult = USD_PER_PRICE_UNIT_PER_LOT[signal.symbol]
    slice_lot, total, stop_risk, budget_note = _pick_four_slices(
        signal.symbol, signal.dist_entry_stop, risk_usd
    )
    tps = (
        signal.take_profit_1,
        signal.take_profit_2,
        signal.take_profit_3,
        signal.take_profit_4,
    )
    actions = (
        "Clôturer 25 % ; stop reliquat → entrée",
        "Clôturer 25 %",
        "Clôturer 25 %",
        "Clôturer 25 % (dernier quart)",
    )
    slices: list[TpSlice] = []
    ladder_total = 0.0
    for i, (tp, action) in enumerate(zip(tps, actions, strict=True), start=1):
        dist = _tp_distance(signal, tp)
        usd = round(slice_lot * dist * mult, 2)
        ladder_total += usd
        act = action.replace("25 %", f"{slice_lot:.3f} lot")
        if i == 1:
            act = f"Clôturer {slice_lot:.3f} lot ; stop du reliquat → entrée"
        elif i == 4:
            act = f"Clôturer {slice_lot:.3f} lot (dernier quart)"
        else:
            act = f"Clôturer {slice_lot:.3f} lot"
        slices.append(
            TpSlice(index=i, price=tp, lots=slice_lot, usd_locked=usd, action_fr=act)
        )

    remainder_risk = round(stop_risk * 0.75, 2)
    after = (
        f"Avant TP1 : ~{stop_risk} USD au stop sur {total:.3f} lot. "
        f"Après TP1 ({slice_lot:.3f} lot sorti) : ~{remainder_risk} USD tant que le stop n'est pas à l'entrée ; "
        f"puis ~0 USD sur le reliquat (spread à part)."
    )
    tp_line = " / ".join(f"{t:.2f}" for t in tps)
    order = (
        f"{signal.order_type_fr} à {signal.entry_mid:.2f}, {total:.3f} lot "
        f"(4×{slice_lot:.3f}), stop {signal.stop_loss:.2f}, "
        f"TP {tp_line}."
    )
    return LadderSizing(
        symbol=signal.symbol,
        risk_budget_usd=risk_usd,
        slice_lots=slice_lot,
        total_lots=total,
        total_risk_at_stop_usd=stop_risk,
        risk_budget_note_fr=budget_note,
        order_summary_fr=order,
        broker_note_fr=BROKER_MILLI_NOTE_FR,
        slices=tuple(slices),
        risk_after_tp1_note_fr=after,
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
    ladder = build_week_ladder(signal, WEEK_RISK_USD)
    return SymbolSizing(
        symbol=sym,
        usd_per_price_001_lot=round(mult * 0.001, 4),
        usd_per_price_1_lot=mult,
        rows=rows,
        week_ladder=ladder,
    )
