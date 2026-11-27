"""Twelve experimental strategy hypotheses (LOT-006).

These are research hypotheses only:
- status = hypothesis
- edge_demonstrated = False
- auto_activate = False / live_allowed = False
- emit BUY / SELL / HOLD / EXIT candidate signals
- never place orders
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import pandas as pd

from quant_deriv_ai.indicators import core as ind
from quant_deriv_ai.strategies.base import BaseStrategy, StrategyError
from quant_deriv_ai.strategies.models import (
    SignalType,
    StrategyCategory,
    StrategySpec,
    StrategyStatus,
)

StrategyFactory = Callable[[StrategySpec, Mapping[str, Any] | None], BaseStrategy]


def _as_hold_warmup(mask_ready: pd.Series, buy: pd.Series, sell: pd.Series) -> list[SignalType]:
    """Map boolean buy/sell masks to SignalType; EXIT on opposing flip after entry."""
    out: list[SignalType] = []
    position = 0  # 1 long, -1 short, 0 flat
    ready = mask_ready.fillna(False).to_numpy(dtype=bool)
    buys = buy.fillna(False).to_numpy(dtype=bool)
    sells = sell.fillna(False).to_numpy(dtype=bool)
    for i in range(len(ready)):
        if not ready[i]:
            out.append(SignalType.HOLD)
            continue
        if position == 0:
            if buys[i]:
                position = 1
                out.append(SignalType.BUY)
            elif sells[i]:
                position = -1
                out.append(SignalType.SELL)
            else:
                out.append(SignalType.HOLD)
        elif position == 1:
            if sells[i]:
                position = 0
                out.append(SignalType.EXIT)
            elif buys[i]:
                out.append(SignalType.HOLD)
            else:
                out.append(SignalType.HOLD)
        else:  # short
            if buys[i]:
                position = 0
                out.append(SignalType.EXIT)
            elif sells[i]:
                out.append(SignalType.HOLD)
            else:
                out.append(SignalType.HOLD)
    return out


def _cross_up(a: pd.Series, b: pd.Series) -> pd.Series:
    prev_a = a.shift(1)
    prev_b = b.shift(1)
    return (prev_a <= prev_b) & (a > b)


def _cross_down(a: pd.Series, b: pd.Series) -> pd.Series:
    prev_a = a.shift(1)
    prev_b = b.shift(1)
    return (prev_a >= prev_b) & (a < b)


# ----- concrete strategies -------------------------------------------------


class SmaCrossoverStrategy(BaseStrategy):
    def _compute(self, frame: pd.DataFrame) -> list[SignalType]:
        fast_n = int(self.params["fast"])
        slow_n = int(self.params["slow"])
        if fast_n >= slow_n:
            raise StrategyError("sma_crossover: fast must be < slow")
        close = frame["close"].astype(float)
        fast = ind.sma(close, fast_n)
        slow = ind.sma(close, slow_n)
        ready = fast.notna() & slow.notna()
        return _as_hold_warmup(ready, _cross_up(fast, slow), _cross_down(fast, slow))


class EmaCrossoverStrategy(BaseStrategy):
    def _compute(self, frame: pd.DataFrame) -> list[SignalType]:
        fast_n = int(self.params["fast"])
        slow_n = int(self.params["slow"])
        if fast_n >= slow_n:
            raise StrategyError("ema_crossover: fast must be < slow")
        close = frame["close"].astype(float)
        fast = ind.ema(close, fast_n)
        slow = ind.ema(close, slow_n)
        ready = fast.notna() & slow.notna()
        return _as_hold_warmup(ready, _cross_up(fast, slow), _cross_down(fast, slow))


class RsiMeanReversionStrategy(BaseStrategy):
    def _compute(self, frame: pd.DataFrame) -> list[SignalType]:
        period = int(self.params["period"])
        low = float(self.params["oversold"])
        high = float(self.params["overbought"])
        close = frame["close"].astype(float)
        rsi = ind.rsi(close, period)
        prev = rsi.shift(1)
        buy = (prev <= low) & (rsi > low)
        sell = (prev >= high) & (rsi < high)
        return _as_hold_warmup(rsi.notna(), buy, sell)


class MacdCrossStrategy(BaseStrategy):
    def _compute(self, frame: pd.DataFrame) -> list[SignalType]:
        close = frame["close"].astype(float)
        macd_df = ind.macd(
            close,
            fast=int(self.params["fast"]),
            slow=int(self.params["slow"]),
            signal=int(self.params["signal"]),
        )
        line = macd_df["macd"]
        sig = macd_df["macd_signal"]
        ready = line.notna() & sig.notna()
        return _as_hold_warmup(ready, _cross_up(line, sig), _cross_down(line, sig))


class BollingerReversionStrategy(BaseStrategy):
    def _compute(self, frame: pd.DataFrame) -> list[SignalType]:
        close = frame["close"].astype(float)
        bb = ind.bollinger(
            close,
            period=int(self.params["period"]),
            num_std=float(self.params["num_std"]),
        )
        upper = bb["bb_upper"]
        lower = bb["bb_lower"]
        mid = bb["bb_mid"]
        prev = close.shift(1)
        buy = (prev <= lower) & (close > lower)
        sell = (prev >= upper) & (close < upper)
        # Exit toward mid after entry is handled by opposing signals via EXIT.
        _ = mid
        return _as_hold_warmup(upper.notna() & lower.notna(), buy, sell)


class DonchianBreakoutStrategy(BaseStrategy):
    def _compute(self, frame: pd.DataFrame) -> list[SignalType]:
        period = int(self.params["period"])
        # Prior-channel levels (no look-ahead): use shift(1) of Donchian.
        high = frame["high"].astype(float)
        low = frame["low"].astype(float)
        close = frame["close"].astype(float)
        dc = ind.donchian(high, low, period=period)
        upper = dc["donchian_upper"].shift(1)
        lower = dc["donchian_lower"].shift(1)
        buy = close > upper
        sell = close < lower
        ready = upper.notna() & lower.notna()
        return _as_hold_warmup(ready, buy, sell)


class MomentumFollowStrategy(BaseStrategy):
    def _compute(self, frame: pd.DataFrame) -> list[SignalType]:
        period = int(self.params["period"])
        thr = float(self.params["threshold"])
        close = frame["close"].astype(float)
        mom = ind.momentum(close, period)
        prev = mom.shift(1)
        buy = (prev <= thr) & (mom > thr)
        sell = (prev >= -thr) & (mom < -thr)
        return _as_hold_warmup(mom.notna(), buy, sell)


class AdxTrendStrategy(BaseStrategy):
    def _compute(self, frame: pd.DataFrame) -> list[SignalType]:
        period = int(self.params["period"])
        min_adx = float(self.params["min_adx"])
        high = frame["high"].astype(float)
        low = frame["low"].astype(float)
        close = frame["close"].astype(float)
        adx_df = ind.adx(high, low, close, period=period)
        adx = adx_df["adx"]
        plus_di = adx_df["plus_di"]
        minus_di = adx_df["minus_di"]
        trending = adx >= min_adx
        buy = trending & _cross_up(plus_di, minus_di)
        sell = trending & _cross_down(plus_di, minus_di)
        ready = adx.notna() & plus_di.notna() & minus_di.notna()
        return _as_hold_warmup(ready, buy, sell)


class StochasticReversionStrategy(BaseStrategy):
    def _compute(self, frame: pd.DataFrame) -> list[SignalType]:
        high = frame["high"].astype(float)
        low_s = frame["low"].astype(float)
        close = frame["close"].astype(float)
        stoch = ind.stochastic(
            high,
            low_s,
            close,
            k_period=int(self.params["k_period"]),
            d_period=int(self.params["d_period"]),
        )
        k = stoch["stoch_k"]
        low = float(self.params["oversold"])
        high_thr = float(self.params["overbought"])
        prev = k.shift(1)
        buy = (prev <= low) & (k > low)
        sell = (prev >= high_thr) & (k < high_thr)
        return _as_hold_warmup(k.notna(), buy, sell)


class AtrBreakoutStrategy(BaseStrategy):
    def _compute(self, frame: pd.DataFrame) -> list[SignalType]:
        period = int(self.params["period"])
        mult = float(self.params["multiplier"])
        high = frame["high"].astype(float)
        low = frame["low"].astype(float)
        close = frame["close"].astype(float)
        atr = ind.atr(high, low, close, period=period)
        # Causal channel: prior close ± mult * prior ATR
        basis = close.shift(1)
        width = atr.shift(1) * mult
        upper = basis + width
        lower = basis - width
        buy = close > upper
        sell = close < lower
        ready = atr.notna() & basis.notna()
        return _as_hold_warmup(ready, buy, sell)


class DualMaRsiFilterStrategy(BaseStrategy):
    def _compute(self, frame: pd.DataFrame) -> list[SignalType]:
        fast_n = int(self.params["fast"])
        slow_n = int(self.params["slow"])
        rsi_period = int(self.params["rsi_period"])
        rsi_low = float(self.params["rsi_low"])
        rsi_high = float(self.params["rsi_high"])
        if fast_n >= slow_n:
            raise StrategyError("dual_ma_rsi_filter: fast must be < slow")
        close = frame["close"].astype(float)
        fast = ind.sma(close, fast_n)
        slow = ind.sma(close, slow_n)
        rsi = ind.rsi(close, rsi_period)
        buy = _cross_up(fast, slow) & (rsi < rsi_high)
        sell = _cross_down(fast, slow) & (rsi > rsi_low)
        ready = fast.notna() & slow.notna() & rsi.notna()
        return _as_hold_warmup(ready, buy, sell)


class WilliamsRReversionStrategy(BaseStrategy):
    def _compute(self, frame: pd.DataFrame) -> list[SignalType]:
        period = int(self.params["period"])
        oversold = float(self.params["oversold"])
        overbought = float(self.params["overbought"])
        high = frame["high"].astype(float)
        low = frame["low"].astype(float)
        close = frame["close"].astype(float)
        wr = ind.williams_r(high, low, close, period=period)
        prev = wr.shift(1)
        # Williams %R: -100 oversold, 0 overbought
        buy = (prev <= oversold) & (wr > oversold)
        sell = (prev >= overbought) & (wr < overbought)
        return _as_hold_warmup(wr.notna(), buy, sell)


# ----- catalog -------------------------------------------------------------

_SPECS: list[tuple[StrategySpec, type[BaseStrategy]]] = [
    (
        StrategySpec(
            id="STR-001",
            name="sma_crossover",
            category=StrategyCategory.TREND,
            status=StrategyStatus.HYPOTHESIS,
            description="Simple moving-average fast/slow crossover",
            hypothesis=(
                "Causal SMA fast/slow crosses identify short-horizon trend persistence "
                "without claiming a demonstrated edge."
            ),
            default_params={"fast": 10, "slow": 30},
        ),
        SmaCrossoverStrategy,
    ),
    (
        StrategySpec(
            id="STR-002",
            name="ema_crossover",
            category=StrategyCategory.TREND,
            status=StrategyStatus.HYPOTHESIS,
            description="Exponential moving-average fast/slow crossover",
            hypothesis=(
                "EMA crosses respond faster than SMA and may capture early trend shifts "
                "(hypothesis only)."
            ),
            default_params={"fast": 12, "slow": 26},
        ),
        EmaCrossoverStrategy,
    ),
    (
        StrategySpec(
            id="STR-003",
            name="rsi_mean_reversion",
            category=StrategyCategory.MEAN_REVERSION,
            status=StrategyStatus.HYPOTHESIS,
            description="RSI threshold mean-reversion entries",
            hypothesis=(
                "RSI exits from oversold/overbought zones mean-revert on short horizons "
                "(unproven)."
            ),
            default_params={"period": 14, "oversold": 30.0, "overbought": 70.0},
        ),
        RsiMeanReversionStrategy,
    ),
    (
        StrategySpec(
            id="STR-004",
            name="macd_cross",
            category=StrategyCategory.TREND,
            status=StrategyStatus.HYPOTHESIS,
            description="MACD line vs signal-line crossover",
            hypothesis="MACD/signal crosses proxy momentum regime changes (hypothesis).",
            default_params={"fast": 12, "slow": 26, "signal": 9},
        ),
        MacdCrossStrategy,
    ),
    (
        StrategySpec(
            id="STR-005",
            name="bollinger_reversion",
            category=StrategyCategory.MEAN_REVERSION,
            status=StrategyStatus.HYPOTHESIS,
            description="Bollinger band touch mean-reversion",
            hypothesis=(
                "Closes reclaiming the band after an outside touch revert toward the mid "
                "(hypothesis)."
            ),
            default_params={"period": 20, "num_std": 2.0},
        ),
        BollingerReversionStrategy,
    ),
    (
        StrategySpec(
            id="STR-006",
            name="donchian_breakout",
            category=StrategyCategory.BREAKOUT,
            status=StrategyStatus.HYPOTHESIS,
            description="Donchian channel breakout using prior-channel levels",
            hypothesis=(
                "Breaks of the prior Donchian channel continue in the breakout direction "
                "(hypothesis; causal prior levels)."
            ),
            default_params={"period": 20},
            requires_ohlc=True,
        ),
        DonchianBreakoutStrategy,
    ),
    (
        StrategySpec(
            id="STR-007",
            name="momentum_follow",
            category=StrategyCategory.MOMENTUM,
            status=StrategyStatus.HYPOTHESIS,
            description="Close momentum threshold follow-through",
            hypothesis="Signed close momentum above a threshold persists briefly (hypothesis).",
            default_params={"period": 10, "threshold": 0.0},
        ),
        MomentumFollowStrategy,
    ),
    (
        StrategySpec(
            id="STR-008",
            name="adx_trend",
            category=StrategyCategory.TREND,
            status=StrategyStatus.HYPOTHESIS,
            description="ADX-filtered +DI/-DI crossover",
            hypothesis=(
                "+DI/-DI crosses are more informative when ADX exceeds a floor (hypothesis)."
            ),
            default_params={"period": 14, "min_adx": 20.0},
            requires_ohlc=True,
        ),
        AdxTrendStrategy,
    ),
    (
        StrategySpec(
            id="STR-009",
            name="stochastic_reversion",
            category=StrategyCategory.MEAN_REVERSION,
            status=StrategyStatus.HYPOTHESIS,
            description="Stochastic %K threshold mean-reversion",
            hypothesis="Stochastic %K reclaim from extremes mean-reverts (hypothesis).",
            default_params={
                "k_period": 14,
                "d_period": 3,
                "oversold": 20.0,
                "overbought": 80.0,
            },
            requires_ohlc=True,
        ),
        StochasticReversionStrategy,
    ),
    (
        StrategySpec(
            id="STR-010",
            name="atr_breakout",
            category=StrategyCategory.VOLATILITY,
            status=StrategyStatus.HYPOTHESIS,
            description="ATR volatility channel breakout",
            hypothesis=(
                "Closes beyond prior close ± k·ATR indicate volatility expansion continuation "
                "(hypothesis)."
            ),
            default_params={"period": 14, "multiplier": 1.5},
            requires_ohlc=True,
        ),
        AtrBreakoutStrategy,
    ),
    (
        StrategySpec(
            id="STR-011",
            name="dual_ma_rsi_filter",
            category=StrategyCategory.FILTERED,
            status=StrategyStatus.HYPOTHESIS,
            description="SMA crossover filtered by RSI band",
            hypothesis=(
                "Trend crosses filtered by RSI avoid chasing extremes (hypothesis; unproven)."
            ),
            default_params={
                "fast": 10,
                "slow": 30,
                "rsi_period": 14,
                "rsi_low": 30.0,
                "rsi_high": 70.0,
            },
        ),
        DualMaRsiFilterStrategy,
    ),
    (
        StrategySpec(
            id="STR-012",
            name="williams_r_reversion",
            category=StrategyCategory.MEAN_REVERSION,
            status=StrategyStatus.HYPOTHESIS,
            description="Williams %R threshold mean-reversion",
            hypothesis="Williams %R exits from extremes mean-revert (hypothesis).",
            default_params={"period": 14, "oversold": -80.0, "overbought": -20.0},
            requires_ohlc=True,
        ),
        WilliamsRReversionStrategy,
    ),
]


def all_strategy_specs() -> list[StrategySpec]:
    return [spec for spec, _ in _SPECS]


def strategy_class_map() -> dict[str, type[BaseStrategy]]:
    return {spec.id: cls for spec, cls in _SPECS}


def build_strategy(
    spec: StrategySpec,
    params: Mapping[str, Any] | None = None,
) -> BaseStrategy:
    classes = strategy_class_map()
    cls = classes.get(spec.id)
    if cls is None:
        # Fallback by name for inspect convenience
        by_name = {s.name: c for s, c in _SPECS}
        cls = by_name.get(spec.name)
    if cls is None:
        msg = f"no implementation for strategy {spec.id}/{spec.name}"
        raise StrategyError(msg)
    return cls(spec, params)


def catalog_signal_coverage() -> dict[str, set[str]]:
    """Dev helper: ensure SignalType enum is referenced (static intent)."""
    return {
        "signals": {s.value for s in SignalType},
        "ids": {spec.id for spec, _ in _SPECS},
    }
