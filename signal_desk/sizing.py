"""Position sizing — Deriv MT5 (min/step 0,01 lot)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from signal_desk.analysis import SignalResult
from signal_desk.deriv_specs import (
    DERIV_MT5,
    DERIV_MT5_NOTE_FR,
    DERIV_SPECS_URL,
    DerivSymbolSpec,
)

WEEK_RISK_USD = 50.0
LADDER_SLICES = 4


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
    mode: str  # "single" | "ladder_4x" | "off"
    payout_label_fr: str
    payout_usd: float | None
    slice_lots: float
    total_lots: float
    total_risk_at_stop_usd: float
    risk_budget_note_fr: str | None
    order_summary_fr: str
    broker_note_fr: str
    slices: tuple[TpSlice, ...]
    risk_after_tp1_note_fr: str
    ladder_total_usd: float
    ladder_risk_threshold_usd: float | None


@dataclass(frozen=True)
class SymbolSizing:
    symbol: str
    deriv_spec: DerivSymbolSpec
    rows: list[SizeRow]
    week_ladder: LadderSizing


CONTRACT_NOTE_FR = DERIV_MT5_NOTE_FR


def _spec(symbol: str) -> DerivSymbolSpec:
    return DERIV_MT5[symbol]


def _risk_usd(spec: DerivSymbolSpec, dist_stop: float, lots: float) -> float:
    return round(lots * dist_stop * spec.usd_per_price_unit_per_lot, 2)


def _max_lots_for_budget(spec: DerivSymbolSpec, dist_stop: float, budget: float) -> float:
    if dist_stop <= 0:
        return spec.min_volume
    raw = budget / (dist_stop * spec.usd_per_price_unit_per_lot)
    steps = math.floor(raw / spec.volume_step)
    lots = max(spec.min_volume, steps * spec.volume_step)
    return round(lots, 2)


def _ladder_total_lots(spec: DerivSymbolSpec) -> float:
    return round(LADDER_SLICES * spec.volume_step, 2)


def _ladder_min_risk(spec: DerivSymbolSpec, dist_stop: float) -> float:
    return _risk_usd(spec, dist_stop, _ladder_total_lots(spec))


def _tp_distance(signal: SignalResult, tp_price: float) -> float:
    if signal.side.value == "achat":
        return abs(tp_price - signal.entry_mid)
    return abs(signal.entry_mid - tp_price)


def size_for_risk(symbol: str, dist_stop: float, dist_tp1: float, risk_usd: float) -> SizeRow:
    spec = _spec(symbol)
    lots = _max_lots_for_budget(spec, dist_stop, risk_usd)
    actual = _risk_usd(spec, dist_stop, lots)
    reward = round(lots * dist_tp1 * spec.usd_per_price_unit_per_lot, 2)
    note = None
    ladder_risk = _ladder_min_risk(spec, dist_stop)
    if ladder_risk > risk_usd:
        note = (
            f"Deriv MT5 : échelle 4×{spec.volume_step:.2f} lot nécessite "
            f"{_ladder_total_lots(spec):.2f} lot (~{ladder_risk} USD au stop)."
        )
    return SizeRow(risk_usd, lots, actual, reward, note)


def build_week_ladder(signal: SignalResult, risk_usd: float = WEEK_RISK_USD) -> LadderSizing:
    spec = _spec(signal.symbol)
    dist_stop = signal.dist_entry_stop
    ladder_lots = _ladder_total_lots(spec)
    ladder_risk = _ladder_min_risk(spec, dist_stop)
    tps = (
        signal.take_profit_1,
        signal.take_profit_2,
        signal.take_profit_3,
        signal.take_profit_4,
    )

    if ladder_risk > risk_usd + 0.01 and signal.symbol == "XAGUSD":
        note = (
            f"XAGUSD hors phase {risk_usd:.0f} USD : 0,04 lot → ~{ladder_risk} USD au stop "
            f"(> {risk_usd:.0f} USD). Pas d’ordre argent à ce budget."
        )
        return LadderSizing(
            symbol=signal.symbol,
            risk_budget_usd=risk_usd,
            mode="off",
            slice_lots=0.0,
            total_lots=0.0,
            total_risk_at_stop_usd=0.0,
            risk_budget_note_fr=note,
            order_summary_fr=note,
            broker_note_fr=DERIV_MT5_NOTE_FR,
            slices=(),
            risk_after_tp1_note_fr="",
            ladder_total_usd=0.0,
            ladder_risk_threshold_usd=ladder_risk,
            payout_label_fr="Hors budget",
            payout_usd=None,
        )

    if ladder_risk > risk_usd + 0.01:
        lots = spec.min_volume
        stop_risk = _risk_usd(spec, dist_stop, lots)
        tp = signal.take_profit_1
        tp_usd = round(lots * signal.dist_entry_tp1 * spec.usd_per_price_unit_per_lot, 2)
        order = (
            f"{signal.order_type_fr} à {signal.entry_mid:.2f}, {lots:.2f} lot (Deriv MT5), "
            f"stop {signal.stop_loss:.2f}, take profit unique {tp:.2f} (~1R, clôture totale)."
        )
        note = (
            f"Sous {risk_usd:.0f} USD de risque : Deriv n’accepte pas 4 partials (min {spec.volume_step:.2f} lot) — "
            f"une seule ligne {lots:.2f} lot (~{stop_risk} USD au stop). "
            f"Échelle 4 TP possible à partir de ~{ladder_risk:.0f} USD au stop "
            f"({ladder_lots:.2f} lot = 4×{spec.volume_step:.2f})."
        )
        slices = (
            TpSlice(
                1,
                tp,
                lots,
                tp_usd,
                "Clôture totale 0,01 lot au TP (~1R) — pas de partial < min Deriv.",
            ),
        )
        after = (
            f"Avant TP : ~{stop_risk} USD au stop sur {lots:.2f} lot. "
            "Pas de reliquat après clôture totale au TP unique."
        )
        broker = (
            f"Deriv MT5 {spec.symbol} : contrat {spec.contract_size:g} {spec.base_unit}/lot, "
            f"min & pas {spec.volume_step:.2f} lot — {DERIV_SPECS_URL}"
        )
        return LadderSizing(
            symbol=signal.symbol,
            risk_budget_usd=risk_usd,
            mode="single",
            slice_lots=lots,
            total_lots=lots,
            total_risk_at_stop_usd=stop_risk,
            risk_budget_note_fr=note,
            order_summary_fr=order,
            broker_note_fr=broker,
            slices=slices,
            risk_after_tp1_note_fr=after,
            ladder_total_usd=tp_usd,
            ladder_risk_threshold_usd=ladder_risk,
            payout_label_fr="Gain TP unique ~",
            payout_usd=tp_usd,
        )

    slice_lot = spec.volume_step
    stop_risk = ladder_risk
    actions = (
        f"Clôturer {slice_lot:.2f} lot ; stop reliquat → entrée",
        f"Clôturer {slice_lot:.2f} lot",
        f"Clôturer {slice_lot:.2f} lot",
        f"Clôturer {slice_lot:.2f} lot (dernier quart)",
    )
    slices_list: list[TpSlice] = []
    total_usd = 0.0
    for i, (tp, action) in enumerate(zip(tps, actions, strict=True), start=1):
        dist = _tp_distance(signal, tp)
        usd = round(slice_lot * dist * spec.usd_per_price_unit_per_lot, 2)
        total_usd += usd
        slices_list.append(TpSlice(i, tp, slice_lot, usd, action))

    remainder = round(stop_risk * 0.75, 2)
    after = (
        f"Avant TP1 : ~{stop_risk} USD au stop. Après TP1 ({slice_lot:.2f} lot sorti) : "
        f"~{remainder} USD tant que le stop n'est pas à l'entrée ; puis ~0 USD sur le reliquat."
    )
    tp_line = " / ".join(f"{t:.2f}" for t in tps)
    order = (
        f"{signal.order_type_fr} à {signal.entry_mid:.2f}, {ladder_lots:.2f} lot "
        f"(4×{slice_lot:.2f} Deriv MT5), stop {signal.stop_loss:.2f}, TP {tp_line}."
    )
    return LadderSizing(
        symbol=signal.symbol,
        risk_budget_usd=risk_usd,
        mode="ladder_4x",
        slice_lots=slice_lot,
        total_lots=ladder_lots,
        total_risk_at_stop_usd=stop_risk,
        risk_budget_note_fr=None,
        order_summary_fr=order,
        broker_note_fr=DERIV_MT5_NOTE_FR,
        slices=tuple(slices_list),
        risk_after_tp1_note_fr=after,
        ladder_total_usd=round(total_usd, 2),
        ladder_risk_threshold_usd=ladder_risk,
        payout_label_fr="Cumul 4 TP ~",
        payout_usd=round(total_usd, 2),
    )


def build_sizing(
    signal: SignalResult, budgets: tuple[float, ...] = (20.0, 50.0, 100.0)
) -> SymbolSizing:
    spec = _spec(signal.symbol)
    rows = [
        size_for_risk(signal.symbol, signal.dist_entry_stop, signal.dist_entry_tp1, b)
        for b in budgets
    ]
    ladder = build_week_ladder(signal, WEEK_RISK_USD)
    return SymbolSizing(
        symbol=signal.symbol,
        deriv_spec=spec,
        rows=rows,
        week_ladder=ladder,
    )
