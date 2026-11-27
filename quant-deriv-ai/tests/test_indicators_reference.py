"""Compare vectorized indicators against independent reference loops."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_deriv_ai.indicators.core import (
    atr,
    bollinger,
    donchian,
    ema,
    historical_volatility,
    macd,
    momentum,
    roc,
    rsi,
    sma,
    stochastic,
    williams_r,
)
from tests.conftest_ta import make_ohlc, ref_atr, ref_ema, ref_sma


@pytest.fixture
def ohlc() -> pd.DataFrame:
    return make_ohlc(250, seed=7)


def test_sma_matches_reference(ohlc: pd.DataFrame) -> None:
    period = 20
    got = sma(ohlc["close"], period).to_numpy()
    exp = ref_sma(ohlc["close"].to_numpy(), period)
    mask = ~np.isnan(exp)
    np.testing.assert_allclose(got[mask], exp[mask], rtol=1e-10, atol=1e-10)
    assert np.all(np.isnan(got[~mask]))


def test_ema_matches_reference_recursive(ohlc: pd.DataFrame) -> None:
    period = 20
    got = ema(ohlc["close"], period).to_numpy()
    exp = ref_ema(ohlc["close"].to_numpy(), period)
    mask = ~np.isnan(exp) & ~np.isnan(got)
    # Same recursive adjust=False seed (first value) → close match after warmup.
    np.testing.assert_allclose(got[mask], exp[mask], rtol=1e-9, atol=1e-9)


def test_rsi_bounded(ohlc: pd.DataFrame) -> None:
    values = rsi(ohlc["close"], 14).dropna()
    assert not values.empty
    assert float(values.min()) >= 0.0
    assert float(values.max()) <= 100.0


def test_atr_matches_wilder_reference(ohlc: pd.DataFrame) -> None:
    period = 14
    got = atr(ohlc["high"], ohlc["low"], ohlc["close"], period).to_numpy()
    exp = ref_atr(
        ohlc["high"].to_numpy(),
        ohlc["low"].to_numpy(),
        ohlc["close"].to_numpy(),
        period,
    )
    # Wilder SMA seed vs ewm(alpha=1/n) converge; allow small drift early, tighter late.
    mask = np.arange(len(got)) >= period + 40
    mask &= ~np.isnan(got) & ~np.isnan(exp)
    np.testing.assert_allclose(got[mask], exp[mask], rtol=5e-2, atol=5e-2)


def test_macd_structure(ohlc: pd.DataFrame) -> None:
    out = macd(ohlc["close"])
    assert list(out.columns) == ["macd", "macd_signal", "macd_hist"]
    valid = out.dropna()
    assert not valid.empty
    np.testing.assert_allclose(
        valid["macd_hist"],
        valid["macd"] - valid["macd_signal"],
        rtol=1e-12,
        atol=1e-12,
    )


def test_bollinger_symmetry(ohlc: pd.DataFrame) -> None:
    bb = bollinger(ohlc["close"], 20, 2.0).dropna()
    mid_dist_up = bb["bb_upper"] - bb["bb_mid"]
    mid_dist_dn = bb["bb_mid"] - bb["bb_lower"]
    np.testing.assert_allclose(mid_dist_up, mid_dist_dn, rtol=1e-12, atol=1e-12)


def test_stochastic_bounds(ohlc: pd.DataFrame) -> None:
    st = stochastic(ohlc["high"], ohlc["low"], ohlc["close"]).dropna()
    assert float(st["stoch_k"].min()) >= -1e-9
    assert float(st["stoch_k"].max()) <= 100.0 + 1e-9


def test_donchian_contains_close_window(ohlc: pd.DataFrame) -> None:
    period = 20
    dc = donchian(ohlc["high"], ohlc["low"], period)
    # At each confirmed bar, channel high >= that bar's high (by construction).
    for i in range(period - 1, len(ohlc)):
        assert dc["donchian_upper"].iloc[i] >= ohlc["high"].iloc[i] - 1e-12
        assert dc["donchian_lower"].iloc[i] <= ohlc["low"].iloc[i] + 1e-12


def test_roc_momentum_hist_vol_williams(ohlc: pd.DataFrame) -> None:
    assert not roc(ohlc["close"], 12).dropna().empty
    assert not momentum(ohlc["close"], 10).dropna().empty
    hv = historical_volatility(ohlc["close"], 20).dropna()
    assert float(hv.min()) >= 0.0
    wr = williams_r(ohlc["high"], ohlc["low"], ohlc["close"], 14).dropna()
    assert float(wr.min()) >= -100.0 - 1e-9
    assert float(wr.max()) <= 0.0 + 1e-9


def test_no_lookahead_mutating_future_bar(ohlc: pd.DataFrame) -> None:
    """Changing the last bar must not alter earlier indicator outputs."""
    period = 20
    base = sma(ohlc["close"], period)
    mutated = ohlc.copy()
    mutated.loc[mutated.index[-1], "close"] = float(mutated["close"].iloc[-1]) * 1.5
    mutated.loc[mutated.index[-1], "high"] = max(
        float(mutated["high"].iloc[-1]), float(mutated["close"].iloc[-1])
    )
    alt = sma(mutated["close"], period)
    # All but the last value must match.
    np.testing.assert_allclose(
        base.iloc[:-1].to_numpy(),
        alt.iloc[:-1].to_numpy(),
        equal_nan=True,
    )


def test_prefix_stability_no_lookahead(ohlc: pd.DataFrame) -> None:
    """Indicator on prefix equals prefix of full-series indicator (causality)."""
    period = 14
    full = rsi(ohlc["close"], period)
    cut = 100
    prefix = rsi(ohlc["close"].iloc[:cut], period)
    np.testing.assert_allclose(
        full.iloc[:cut].to_numpy(),
        prefix.to_numpy(),
        equal_nan=True,
        rtol=1e-12,
        atol=1e-12,
    )
