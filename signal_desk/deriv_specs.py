"""Deriv MT5 symbol specs (public page — confirm in terminal Specification)."""

from __future__ import annotations

from dataclasses import dataclass

# Source: https://trade.deriv.com/trading-specifications (Deriv MT5, commodities)
DERIV_SPECS_URL = "https://trade.deriv.com/trading-specifications"

DERIV_MT5_NOTE_FR = (
    "Spécifications Deriv MT5 : vérifiez aussi Propriétés du symbole dans MT5 "
    "(clic droit → Spécification). Source publique : "
    f"{DERIV_SPECS_URL}"
)


@dataclass(frozen=True)
class DerivSymbolSpec:
    symbol: str
    contract_size: float
    base_unit: str
    min_volume: float
    volume_step: float
    vol_limit: float
    usd_per_price_unit_per_lot: float

    @property
    def min_partial_close(self) -> float:
        """MT5 : clôture partielle ≥ volume step (Deriv min 0,01 sur XAU/XAG)."""
        return self.volume_step


DERIV_MT5: dict[str, DerivSymbolSpec] = {
    "XAUUSD": DerivSymbolSpec(
        symbol="XAUUSD",
        contract_size=100.0,
        base_unit="XAU",
        min_volume=0.01,
        volume_step=0.01,
        vol_limit=30.0,
        usd_per_price_unit_per_lot=100.0,
    ),
    "XAGUSD": DerivSymbolSpec(
        symbol="XAGUSD",
        contract_size=5000.0,
        base_unit="XAG",
        min_volume=0.01,
        volume_step=0.01,
        vol_limit=10.0,
        usd_per_price_unit_per_lot=5000.0,
    ),
}
