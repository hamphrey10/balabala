"""Look-ahead / causality guards for quantitative research (LOT-005)."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from quant_deriv_ai.core.exceptions import QuantDerivError
from quant_deriv_ai.quantitative.models import CausalityCheck, CausalityStatus


class CausalityError(QuantDerivError):
    """Raised when a causality invariant is violated."""


def assert_min_forward_lag(lag: int, *, minimum: int = 1) -> int:
    """Reject zero/negative lags that would allow same-bar or future leakage."""
    if lag < minimum:
        raise CausalityError(
            f"forward_lag={lag} < minimum={minimum} — would introduce look-ahead"
        )
    return lag


def forward_returns(
    close: pd.Series,
    *,
    lag: int = 1,
    horizon: int = 1,
    method: str = "log",
) -> pd.Series:
    """Return from ``t+lag`` to ``t+lag+horizon-1`` aligned to signal time ``t``.

    At index ``t`` the value uses only prices at ``t+lag`` … ``t+lag+horizon``.
    The last ``lag+horizon`` bars are NaN (no future available yet).
    """
    assert_min_forward_lag(lag)
    if horizon < 1:
        raise CausalityError(f"forward_horizon must be >= 1, got {horizon}")
    prices = close.astype(float)
    # Price at start of forward window (exclusive of signal bar when lag>=1)
    start = prices.shift(-lag)
    end = prices.shift(-(lag + horizon))
    method_key = method.strip().lower()
    if method_key == "log":
        out = np.log(end / start)
    elif method_key == "simple":
        out = end / start - 1.0
    else:
        raise CausalityError(f"unsupported return method: {method!r}")
    out.name = f"fwd_ret_lag{lag}_h{horizon}"
    return out


def check_prefix_stability(
    compute: Callable[[pd.Series], pd.Series],
    series: pd.Series,
    *,
    prefix_len: int | None = None,
    name: str = "prefix_stability",
    atol: float = 1e-10,
) -> CausalityCheck:
    """Recompute on a prefix; earlier values must match the full-series result."""
    n = len(series)
    if n < 4:
        return CausalityCheck(
            name=name,
            status=CausalityStatus.SKIPPED,
            detail="series too short for prefix stability check",
        )
    cut = prefix_len if prefix_len is not None else max(n // 2, 2)
    cut = min(max(cut, 2), n - 1)
    full = compute(series)
    prefix = compute(series.iloc[:cut])
    left = full.iloc[:cut].to_numpy(dtype=float)
    right = prefix.to_numpy(dtype=float)
    # Compare where both finite
    mask = np.isfinite(left) & np.isfinite(right)
    if not np.any(mask):
        return CausalityCheck(
            name=name,
            status=CausalityStatus.SKIPPED,
            detail="no overlapping finite values to compare",
        )
    if np.allclose(left[mask], right[mask], atol=atol, equal_nan=False):
        return CausalityCheck(
            name=name,
            status=CausalityStatus.PASS,
            detail=f"prefix_len={cut} matches full-series values",
        )
    return CausalityCheck(
        name=name,
        status=CausalityStatus.FAIL,
        detail=f"prefix_len={cut} diverged from full-series (possible look-ahead)",
    )


def check_future_mutation(
    compute: Callable[[pd.Series], pd.Series],
    series: pd.Series,
    *,
    name: str = "future_mutation",
    atol: float = 1e-10,
) -> CausalityCheck:
    """Mutate the last value; earlier outputs must stay identical."""
    n = len(series)
    if n < 3:
        return CausalityCheck(
            name=name,
            status=CausalityStatus.SKIPPED,
            detail="series too short for future mutation check",
        )
    base = compute(series)
    mutated = series.copy()
    last = float(mutated.iloc[-1]) if np.isfinite(mutated.iloc[-1]) else 0.0
    mutated.iloc[-1] = last * 1.05 + 1.0
    alt = compute(mutated)
    left = base.iloc[:-1].to_numpy(dtype=float)
    right = alt.iloc[:-1].to_numpy(dtype=float)
    mask = np.isfinite(left) | np.isfinite(right)
    # Where either side is finite they must match (NaN patterns included via equal_nan)
    if np.allclose(left, right, atol=atol, equal_nan=True):
        return CausalityCheck(
            name=name,
            status=CausalityStatus.PASS,
            detail="mutating last bar did not change earlier values",
        )
    # Count mismatches among originally finite
    mism = int(np.sum(~np.isclose(left[mask], right[mask], atol=atol, equal_nan=True)))
    return CausalityCheck(
        name=name,
        status=CausalityStatus.FAIL,
        detail=f"mutating last bar changed {mism} earlier value(s)",
    )


def check_forward_return_ignores_signal_bar(
    close: pd.Series,
    *,
    lag: int = 1,
    horizon: int = 1,
    name: str = "forward_returns_ignores_signal_bar",
    atol: float = 1e-10,
) -> CausalityCheck:
    """Mutating ``close[t]`` must not change ``forward_returns[t]`` when ``lag >= 1``."""
    assert_min_forward_lag(lag)
    n = len(close)
    if n < lag + horizon + 2:
        return CausalityCheck(
            name=name,
            status=CausalityStatus.SKIPPED,
            detail="series too short for signal-bar independence check",
        )
    base = forward_returns(close, lag=lag, horizon=horizon)
    # Pick a mid index that has a finite forward return
    idx = None
    for i in range(n - lag - horizon):
        if np.isfinite(base.iloc[i]):
            idx = i
            break
    if idx is None:
        return CausalityCheck(
            name=name,
            status=CausalityStatus.SKIPPED,
            detail="no finite forward return to probe",
        )
    mutated = close.copy()
    last = float(mutated.iloc[idx]) if np.isfinite(mutated.iloc[idx]) else 0.0
    mutated.iloc[idx] = last * 1.25 + 1.0
    alt = forward_returns(mutated, lag=lag, horizon=horizon)
    left = base.iloc[idx]
    right = alt.iloc[idx]
    if np.isfinite(left) and np.isfinite(right) and abs(float(left) - float(right)) <= atol:
        return CausalityCheck(
            name=name,
            status=CausalityStatus.PASS,
            detail=f"forward_returns[{idx}] independent of close[{idx}] (lag={lag})",
        )
    if not np.isfinite(left) and not np.isfinite(right):
        return CausalityCheck(
            name=name,
            status=CausalityStatus.PASS,
            detail=f"both NaN at idx={idx}",
        )
    return CausalityCheck(
        name=name,
        status=CausalityStatus.FAIL,
        detail=f"forward_returns[{idx}] changed when close[{idx}] mutated",
    )


def run_causality_suite(
    close: pd.Series,
    *,
    lag: int = 1,
    horizon: int = 1,
) -> list[CausalityCheck]:
    """Standard causality checks for returns + forward returns.

    Note: ``forward_returns`` *labels* intentionally use future prices relative to
    signal time ``t``. We therefore do **not** run ``check_future_mutation`` on
    them (mutating the last bar must change earlier labels). Instead we verify
    that ``forward_returns[t]`` does not depend on ``close[t]`` when ``lag >= 1``.
    """
    from quant_deriv_ai.quantitative.stats_lab import compute_returns, rolling_mean

    checks: list[CausalityCheck] = [
        CausalityCheck(
            name="min_forward_lag",
            status=CausalityStatus.PASS if lag >= 1 else CausalityStatus.FAIL,
            detail=f"forward_lag={lag}",
        ),
        check_prefix_stability(
            lambda s: compute_returns(s, method="log"),
            close,
            name="returns_prefix_stability",
        ),
        check_future_mutation(
            lambda s: compute_returns(s, method="log"),
            close,
            name="returns_future_mutation",
        ),
        check_prefix_stability(
            lambda s: rolling_mean(s, 10),
            close,
            name="rolling_mean_prefix_stability",
        ),
        check_future_mutation(
            lambda s: rolling_mean(s, 10),
            close,
            name="rolling_mean_future_mutation",
        ),
        check_prefix_stability(
            lambda s: forward_returns(s, lag=lag, horizon=horizon),
            close,
            name="forward_returns_prefix_stability",
        ),
        check_forward_return_ignores_signal_bar(
            close,
            lag=lag,
            horizon=horizon,
        ),
    ]
    return checks
