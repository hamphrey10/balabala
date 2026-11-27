"""Tests for typed domain models and exceptions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from quant_deriv_ai.core.exceptions import TradingModeError
from quant_deriv_ai.core.models import InstrumentRef, OrderSide, SignalIntent, TradingMode
from quant_deriv_ai.security.guards import assert_demo_only, redact_secrets


def test_instrument_ref_frozen() -> None:
    ref = InstrumentRef(symbol="Volatility 75 Index")
    assert ref.symbol == "Volatility 75 Index"
    with pytest.raises(ValidationError):
        ref.symbol = "X"  # type: ignore[misc]


def test_signal_intent_requires_positive_volume() -> None:
    with pytest.raises(ValidationError):
        SignalIntent(symbol="EURUSD", side=OrderSide.BUY, volume=0)


def test_assert_demo_only_rejects_live() -> None:
    assert assert_demo_only(TradingMode.DEMO) is TradingMode.DEMO
    with pytest.raises(TradingModeError):
        assert_demo_only(TradingMode.LIVE)


def test_redact_secrets() -> None:
    data = {"mt5_password": "secret", "server": "Demo", "nested": {"api_key": "x"}}
    out = redact_secrets(data)
    assert out["mt5_password"] == "***REDACTED***"
    assert out["server"] == "Demo"
    assert out["nested"]["api_key"] == "***REDACTED***"
