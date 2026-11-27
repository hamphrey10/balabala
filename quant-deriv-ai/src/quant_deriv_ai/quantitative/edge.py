"""Edge metrics for research probes (LOT-005) — never places orders."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from quant_deriv_ai.core.exceptions import QuantDerivError
from quant_deriv_ai.quantitative.causality import assert_min_forward_lag, forward_returns
from quant_deriv_ai.quantitative.models import EdgeMetrics, EdgeVerdict

# Per-active-signal Sharpe (mean/std, NOT calendar-annualized).
# 0.05 is a conservative research gate for sparse probes.
_CANDIDATE_SHARPE_MIN = 0.05


class EdgeError(QuantDerivError):
    """Raised for invalid edge-evaluation inputs."""


def evaluate_edge(
    signal: pd.Series,
    close: pd.Series,
    *,
    probe_name: str,
    forward_lag: int = 1,
    forward_horizon: int = 1,
    method: str = "log",
    min_observations: int = 30,
) -> EdgeMetrics:
    """Evaluate a causal signal against forward returns.

    ``signal`` at bar ``t`` is paired with the forward return that starts at
    ``t+forward_lag`` (never same-bar).

    Counting rules (reconcile):

    - Warmup / undefined (NaN) signals are **excluded** from ``observations``.
    - Among defined signals with a finite forward return: zero → abstain, else active.
    - ``abstain_rate = (observations - active_signals) / observations``.

    ``sharpe`` is the per-active-signal mean/std of signed PnL (not annualized).
    Sparse probes must not be scaled by ``sqrt(252)`` as if they were daily bars.
    """
    assert_min_forward_lag(forward_lag)
    if forward_horizon < 1:
        raise EdgeError(f"forward_horizon must be >= 1, got {forward_horizon}")
    if len(signal) != len(close):
        raise EdgeError("signal and close must have the same length")

    fwd = forward_returns(close, lag=forward_lag, horizon=forward_horizon, method=method)
    sig = signal.astype(float)
    # Defined signal + usable forward return (warmup NaNs excluded).
    eligible = sig.notna() & fwd.notna()
    n_total = int(eligible.sum())
    active_mask = eligible & (sig != 0.0)
    active = int(active_mask.sum())
    abstain_rate = float((n_total - active) / n_total) if n_total else None

    if active == 0:
        return EdgeMetrics(
            probe_name=probe_name,
            forward_lag=forward_lag,
            forward_horizon=forward_horizon,
            observations=n_total,
            active_signals=0,
            abstain_rate=abstain_rate,
            verdict=EdgeVerdict.INSUFFICIENT_DATA,
            notes="no active (non-zero) signals overlapping forward returns",
        )

    # Signed PnL proxy: sign(signal) * forward_return
    signed = np.sign(sig[active_mask].to_numpy(dtype=float)) * fwd[active_mask].to_numpy(
        dtype=float
    )
    hit_rate = float(np.mean(signed > 0.0))
    expectancy = float(np.mean(signed))
    wins = signed[signed > 0.0]
    losses = signed[signed < 0.0]
    avg_win = float(np.mean(wins)) if wins.size else None
    avg_loss = float(np.mean(losses)) if losses.size else None
    gross_profit = float(wins.sum()) if wins.size else 0.0
    gross_loss = float(-losses.sum()) if losses.size else 0.0
    if gross_loss > 0.0:
        profit_factor: float | None = gross_profit / gross_loss
    elif gross_profit > 0.0:
        profit_factor = float("inf")
    else:
        profit_factor = None

    # Per-trade Sharpe — do NOT annualize sparse/irregular active-signal returns.
    sharpe: float | None = None
    if signed.size > 1:
        std = float(np.std(signed, ddof=1))
        if std > 0.0:
            sharpe = float(np.mean(signed) / std)

    max_dd = _max_drawdown(signed)
    mean_fwd = float(np.mean(fwd[active_mask].to_numpy(dtype=float)))

    verdict = _classify_verdict(
        active=active,
        min_observations=min_observations,
        hit_rate=hit_rate,
        expectancy=expectancy,
        sharpe=sharpe,
    )
    notes = (
        "Research probe only — not a trading strategy; no orders. "
        f"verdict={verdict.value}. "
        "sharpe=per-active-signal mean/std (not calendar-annualized)."
    )
    # Replace inf for JSON/Pydantic friendliness
    if profit_factor is None or not np.isfinite(profit_factor):
        pf: float | None = None
    else:
        pf = profit_factor
    if profit_factor is not None and not np.isfinite(profit_factor):
        notes += " profit_factor undefined (no losses)."

    return EdgeMetrics(
        probe_name=probe_name,
        forward_lag=forward_lag,
        forward_horizon=forward_horizon,
        observations=n_total,
        active_signals=active,
        abstain_rate=abstain_rate,
        hit_rate=hit_rate,
        expectancy=expectancy,
        profit_factor=pf,
        avg_win=avg_win,
        avg_loss=avg_loss,
        sharpe=sharpe,
        max_drawdown=max_dd,
        mean_forward_return=mean_fwd,
        verdict=verdict,
        notes=notes,
    )


def momentum_sign_probe(close: pd.Series, *, lookback: int = 10) -> pd.Series:
    """Research probe: sign of causal momentum over ``lookback`` bars.

    Uses ``close[t] / close[t-lookback] - 1`` — no future prices.
    """
    if lookback < 1:
        raise EdgeError(f"lookback must be >= 1, got {lookback}")
    mom = close.astype(float) / close.astype(float).shift(lookback) - 1.0
    return pd.Series(np.sign(mom.to_numpy(dtype=float)), index=close.index, name="mom_sign")


def rsi_threshold_probe(
    close: pd.Series,
    *,
    period: int = 14,
    low: float = 30.0,
    high: float = 70.0,
) -> pd.Series:
    """Research probe: +1 when RSI < low, -1 when RSI > high, else 0.

    RSI is computed via the shared causal indicator implementation.
    """
    from quant_deriv_ai.indicators.core import compute_from_ohlc

    # Minimal OHLC frame for indicator dispatch
    c = close.astype(float)
    frame = pd.DataFrame(
        {
            "open": c,
            "high": c,
            "low": c,
            "close": c,
        }
    )
    rsi = compute_from_ohlc(frame, "rsi", params={"period": period})
    col = rsi.iloc[:, 0] if isinstance(rsi, pd.DataFrame) else rsi
    out = pd.Series(0.0, index=close.index, name="rsi_threshold", dtype=float)
    out = out.mask(col < low, 1.0)
    out = out.mask(col > high, -1.0)
    out = out.where(col.notna(), np.nan)
    return out


def _max_drawdown(signed_pnl: NDArray[np.floating[Any]]) -> float | None:
    """Max drawdown from a starting equity of 0 (HWM seeded before first trade)."""
    if signed_pnl.size == 0:
        return None
    equity = np.concatenate(([0.0], np.cumsum(signed_pnl)))
    peak = np.maximum.accumulate(equity)
    dd = equity - peak
    return float(dd.min())


def _classify_verdict(
    *,
    active: int,
    min_observations: int,
    hit_rate: float,
    expectancy: float,
    sharpe: float | None,
) -> EdgeVerdict:
    if active < min_observations:
        return EdgeVerdict.INSUFFICIENT_DATA
    # Conservative gates on per-active-signal Sharpe (not annualized).
    if expectancy <= 0.0 or hit_rate <= 0.5:
        return EdgeVerdict.NO_EDGE
    if sharpe is not None and sharpe > _CANDIDATE_SHARPE_MIN and hit_rate >= 0.55:
        return EdgeVerdict.CANDIDATE
    if expectancy > 0.0 and hit_rate > 0.5:
        return EdgeVerdict.WEAK
    return EdgeVerdict.NO_EDGE
