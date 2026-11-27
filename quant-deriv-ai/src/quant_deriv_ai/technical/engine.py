"""Technical Analysis Engine — independent of execution / orders (LOT-004)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from quant_deriv_ai.core.exceptions import QuantDerivError
from quant_deriv_ai.core.logging import get_logger
from quant_deriv_ai.indicators.core import compute_from_ohlc
from quant_deriv_ai.indicators.registry import indicator_names, validate_indicator
from quant_deriv_ai.technical.breakouts import detect_breakout
from quant_deriv_ai.technical.models import (
    BreakoutSide,
    StructureBias,
    TechnicalSnapshot,
    TrendDirection,
    TrendState,
    VolumeCaveat,
)
from quant_deriv_ai.technical.mtf import analyze_mtf
from quant_deriv_ai.technical.structure import (
    detect_swings,
    structure_bias_from_swings,
    support_resistance_from_swings,
)
from quant_deriv_ai.technical.trend import classify_trend

log = get_logger(__name__)

DEFAULT_INDICATORS: tuple[str, ...] = (
    "sma",
    "ema",
    "rsi",
    "macd",
    "atr",
    "adx",
    "bollinger",
    "stochastic",
    "donchian",
    "roc",
    "momentum",
    "cci",
    "williams_r",
    "hist_vol",
)


class TechnicalAnalysisError(QuantDerivError):
    """Raised for TA engine input / configuration failures."""


class TechnicalAnalysisEngine:
    """Compute indicators, structure, trend, breakouts, and MTF snapshots.

    This engine never places orders and has no MT5 write APIs.
    """

    def __init__(
        self,
        *,
        volume_is_synthetic: bool = True,
        swing_left: int = 2,
        swing_right: int = 2,
        breakout_lookback: int = 20,
        sma_fast: int = 20,
        sma_slow: int = 50,
    ) -> None:
        self.volume_is_synthetic = volume_is_synthetic
        self.swing_left = swing_left
        self.swing_right = swing_right
        self.breakout_lookback = breakout_lookback
        self.sma_fast = sma_fast
        self.sma_slow = sma_slow

    @classmethod
    def from_config(cls, cfg: Mapping[str, Any] | None = None) -> TechnicalAnalysisEngine:
        raw = dict(cfg or {})
        return cls(
            volume_is_synthetic=bool(raw.get("volume_is_synthetic", True)),
            swing_left=int(raw.get("swing_left", 2)),
            swing_right=int(raw.get("swing_right", 2)),
            breakout_lookback=int(raw.get("breakout_lookback", 20)),
            sma_fast=int(raw.get("sma_fast", 20)),
            sma_slow=int(raw.get("sma_slow", 50)),
        )

    def compute_indicators(
        self,
        frame: pd.DataFrame,
        names: Sequence[str] | None = None,
        *,
        params: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> pd.DataFrame:
        """Return a DataFrame of indicator columns aligned to ``frame`` index."""
        self._require_ohlc(frame)
        selected = list(names) if names is not None else list(DEFAULT_INDICATORS)
        param_map = {str(k).strip().lower(): dict(v) for k, v in (params or {}).items()}
        parts: list[pd.Series | pd.DataFrame] = []
        for name in selected:
            key = str(name).strip().lower()
            validate_indicator(key, param_map.get(key))
            result = compute_from_ohlc(frame, key, params=param_map.get(key))
            parts.append(result)
        if not parts:
            return pd.DataFrame(index=frame.index)
        out = pd.concat(parts, axis=1)
        out.index = frame.index
        return out

    def analyze(
        self,
        frame: pd.DataFrame,
        *,
        symbol: str,
        timeframe: str,
        indicators: Sequence[str] | None = None,
        indicator_params: Mapping[str, Mapping[str, Any]] | None = None,
        mtf_frames: Mapping[str, pd.DataFrame] | None = None,
    ) -> TechnicalSnapshot:
        """Build a :class:`TechnicalSnapshot` for one series (optional MTF)."""
        self._require_ohlc(frame)
        if frame.empty:
            raise TechnicalAnalysisError("cannot analyze empty frame")

        ind_df = self.compute_indicators(frame, indicators, params=indicator_params)
        latest = _latest_finite_map(ind_df)

        times = frame["time"] if "time" in frame.columns else None
        swings = detect_swings(
            frame["high"].astype(float),
            frame["low"].astype(float),
            left=self.swing_left,
            right=self.swing_right,
            times=times,
        )
        levels = support_resistance_from_swings(swings)
        bias = structure_bias_from_swings(swings)
        trend = classify_trend(
            frame,
            fast=self.sma_fast,
            slow=self.sma_slow,
            swing_left=self.swing_left,
            swing_right=self.swing_right,
        )
        # Prefer structure bias from swings on the snapshot root.
        if bias is not StructureBias.UNKNOWN:
            trend = TrendState(
                direction=trend.direction,
                strength=trend.strength,
                adx=trend.adx,
                sma_fast=trend.sma_fast,
                sma_slow=trend.sma_slow,
                structure_bias=bias,
            )
        breakout = detect_breakout(frame, lookback=self.breakout_lookback)

        as_of: datetime | None = None
        if times is not None and len(times):
            as_of = pd.Timestamp(times.iloc[-1]).to_pydatetime()

        volume_present = "volume" in frame.columns or "tick_volume" in frame.columns
        caveat = VolumeCaveat(
            volume_present=volume_present,
            volume_is_synthetic=self.volume_is_synthetic if volume_present else True,
            note=_volume_note(volume_present, self.volume_is_synthetic),
        )

        mtf = (
            analyze_mtf(
                mtf_frames,
                sma_fast=self.sma_fast,
                sma_slow=self.sma_slow,
                swing_left=self.swing_left,
                swing_right=self.swing_right,
            )
            if mtf_frames
            else None
        )
        ind_names = (
            list(indicators) if indicators is not None else list(DEFAULT_INDICATORS)
        )

        return TechnicalSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            as_of=as_of,
            bar_count=len(frame),
            last_close=float(frame["close"].iloc[-1]),
            indicators=latest,
            trend=trend,
            structure_bias=trend.structure_bias,
            swings=swings[-20:],
            support_resistance=levels,
            breakout=breakout,
            mtf=mtf,
            volume=caveat,
            meta={
                "indicator_names": ind_names,
                "breakout_side": breakout.side.value,
                "no_orders": True,
            },
        )

    def analyze_from_store(
        self,
        root: str | Path,
        *,
        symbol: str,
        timeframe: str,
        indicators: Sequence[str] | None = None,
        mtf_timeframes: Sequence[str] | None = None,
    ) -> TechnicalSnapshot:
        """Load working candles from MarketDataStore and analyze."""
        from quant_deriv_ai.market_data.models import SeriesKind
        from quant_deriv_ai.persistence.store import MarketDataStore

        store = MarketDataStore(root)
        frame = store.read_working(symbol=symbol, kind=SeriesKind.CANDLES, timeframe=timeframe)
        if frame.empty:
            raise TechnicalAnalysisError(
                f"no working candles for {symbol} {timeframe} under {root}"
            )
        mtf_frames: dict[str, pd.DataFrame] | None = None
        if mtf_timeframes:
            mtf_frames = {}
            for tf in mtf_timeframes:
                tf_frame = store.read_working(
                    symbol=symbol, kind=SeriesKind.CANDLES, timeframe=tf
                )
                if not tf_frame.empty:
                    mtf_frames[tf] = tf_frame
        return self.analyze(
            frame,
            symbol=symbol,
            timeframe=timeframe,
            indicators=indicators,
            mtf_frames=mtf_frames,
        )

    @staticmethod
    def list_indicators() -> list[str]:
        return indicator_names()

    @staticmethod
    def _require_ohlc(frame: pd.DataFrame) -> None:
        missing = [c for c in ("open", "high", "low", "close") if c not in frame.columns]
        if missing:
            raise TechnicalAnalysisError(f"frame missing OHLC columns: {missing}")


def _volume_note(volume_present: bool, volume_is_synthetic: bool) -> str:
    if volume_present and volume_is_synthetic:
        return "Volume/tick_volume present but treated as synthetic — not real liquidity."
    if not volume_present:
        return "No volume column; volume-based signals disabled."
    return "Volume marked as potentially real by caller — still verify broker semantics."


def _latest_finite_map(frame: pd.DataFrame) -> dict[str, float]:
    out: dict[str, float] = {}
    for col in frame.columns:
        series = frame[col].dropna()
        if series.empty:
            continue
        val = series.iloc[-1]
        if pd.isna(val):
            continue
        out[str(col)] = float(val)
    return out


def empty_snapshot(symbol: str, timeframe: str) -> TechnicalSnapshot:
    from quant_deriv_ai.technical.models import BreakoutEvent

    return TechnicalSnapshot(
        symbol=symbol,
        timeframe=timeframe,
        trend=TrendState(direction=TrendDirection.UNKNOWN, strength=0.0),
        breakout=BreakoutEvent(side=BreakoutSide.NONE, level=0.0, close=0.0),
    )
